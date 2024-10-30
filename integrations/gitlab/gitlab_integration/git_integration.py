from typing import Dict, Any, Literal, Tuple, List, Type

from gitlab.v4.objects import Project
from loguru import logger
from pydantic import Field, BaseModel
from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.core.entities import (
    FILE_PROPERTY_PREFIX,
    SEARCH_PROPERTY_PREFIX,
)
from gitlab_integration.gitlab_service import PROJECTS_CACHE_KEY
from gitlab_integration.utils import get_cached_all_services
from port_ocean.context.event import event
from port_ocean.core.handlers import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    Selector,
    ResourceConfig,
)


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        project_id, ref, base_path = _validate_project_scope(data)
        project = _get_project_from_cache(project_id)

        file_path = pattern.replace(self.prefix, "")
        if base_path:
            file_path = f"{base_path}/{file_path}"
        if not project:
            return None
        logger.info(
            f"Searching for file {file_path} in Project {project_id}: {project.path_with_namespace}, ref {ref}"
        )
        res = await AsyncFetcher.fetch_single(project.files.get, file_path, ref)
        return res.decode().decode("utf-8")


class SearchEntityProcessor(JQEntityProcessor):
    prefix = SEARCH_PROPERTY_PREFIX
    separation_symbol = "&&"

    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """
        Handles entity mapping for search:// pattern
        :param data: project data
        :param pattern: e.g. search://scope=blobs&&query=filename:port.yml
        :return: True if the search pattern matches, False otherwise
        """
        project_id, _, base_path = _validate_project_scope(data)
        scope, query = self._parse_search_pattern(pattern)

        # assuming that the code is being called after event initialization and as part of the GitLab service
        # initialization
        project = _get_project_from_cache(project_id)
        if not project:
            return None
        base_path_message = f" in base path {base_path}" if base_path else ""
        logger.info(
            f"Searching {query} {base_path_message} in Project {project_id}: {project.path_with_namespace}, "
            f"scope {scope}"
        )
        match = None
        if project:
            if scope == "blobs":
                # if the query does not contain a path filter, we add the base path to the query
                # this is done to avoid searching the entire project for the file, if the base path is known
                # having the base path applies to the case where we export a folder as a monorepo
                if base_path and "path:" not in query:
                    query = f"{query} path:{base_path}"
                results = await AsyncFetcher.fetch_single(project.search, scope, query)  # type: ignore
                match = bool(results)
            else:
                results = await AsyncFetcher.fetch_single(project.search, scope, query)  # type: ignore
                match = bool(results)
        return match

    def _parse_search_pattern(self, pattern: str) -> Tuple[str, str]:
        """
        :param pattern: e.g. search://scope=blobs&&query=filename:port.yml
        :return: scope, search_pattern
        """
        # remove prefix
        pattern = pattern.replace(self.prefix, "")
        if len(pattern.split(self.separation_symbol)) == 1:
            raise ValueError(
                f"Search pattern {pattern} does not match the expected format: search://scope=<scope>&&query=<query>"
            )
        scope, query = pattern.split(self.separation_symbol, 1)

        # return the actual scope and query values
        # e.g. scope=blobs -> blobs, query=filename:port.yml -> filename:port.yml
        return scope.split("=")[1], "=".join(query.split("=")[1:])


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            entity_processor = SearchEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)


class FoldersSelector(BaseModel):
    path: str
    repos: List[str] = Field(default_factory=list)
    branch: str | None = None


class GitlabSelector(Selector):
    folders: List[FoldersSelector] = Field(default_factory=list)


class GitlabResourceConfig(ResourceConfig):
    selector: GitlabSelector


class FilesSelector(BaseModel):
    path: str = Field(description="The path to get the files from")
    repos: List[str] = Field(
        description="A list of repositories to search files in", default_factory=list
    )


class GitLabFilesSelector(Selector):
    files: FilesSelector


class GitLabFilesResourceConfig(ResourceConfig):
    selector: GitLabFilesSelector
    kind: Literal["file"]


class GitlabPortAppConfig(PortAppConfig):
    spec_path: str | List[str] = Field(alias="specPath", default="**/port.yml")
    branch: str | None
    filter_owned_projects: bool | None = Field(
        alias="filterOwnedProjects", default=True
    )
    project_visibility_filter: str | None = Field(
        alias="projectVisibilityFilter", default=None
    )
    resources: list[GitLabFilesResourceConfig | GitlabResourceConfig] = Field(default_factory=list)  # type: ignore


def _get_project_from_cache(project_id: int) -> Project | None:
    """
    projects cache structure:
    {
        "token1": {
            "project_id1": Project1,
            "project_id2": Project2,
        },
        "token2": {
            "project_id3": Project3,
            ...
        }
    }
    """
    for token_projects in event.attributes.get(PROJECTS_CACHE_KEY, {}).values():
        if project := token_projects.get(project_id):
            return project
    logger.info(f"Project {project_id} not found in cache, fetching from GitLab")
    # If the project is not found in the cache, it means we have finished collecting information for the previous
    # project entity and have moved on to the next one. In that case we can remove the previous one from the cache
    # since we will not need to use it until the next resync operation
    event.attributes[PROJECTS_CACHE_KEY] = {}
    for service in get_cached_all_services():
        if project := service.gitlab_client.projects.get(project_id):
            event.attributes.setdefault(PROJECTS_CACHE_KEY, {}).setdefault(
                service.gitlab_client.private_token, {}
            )[project_id] = project
            return project
    return None


def _validate_project_scope(data: Dict[str, Any]) -> Tuple[int, str, str]:
    # repo.id can be set when exporting folders as monorepo from a repo
    project_id = data.get("repo", {}).get("id") or data.get("id")
    # __branch is enriched when exporting folders as monorepo from a repo, or when exporting a single repo
    ref = (
        data.get("__branch")
        or data.get("default_branch")
        or data.get("repo", {}).get("default_branch")
    )
    # folder.path is enriched when exporting folders as monorepo from a repo
    path = data.get("folder", {}).get("path", "")
    if project_id and ref:
        return project_id, ref, path
    raise ValueError("Project id and ref are required")
