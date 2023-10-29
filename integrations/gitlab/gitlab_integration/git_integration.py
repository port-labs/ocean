from typing import Dict, Any, Tuple, List, Type

from gitlab_integration.core.entities import (
    FILE_PROPERTY_PREFIX,
    SEARCH_PROPERTY_PREFIX,
)
from loguru import logger
from pydantic import Field
from gitlab.v4.objects import Project
from gitlab_integration.gitlab_service import PROJECTS_CACHE_KEY
from gitlab_integration.utils import get_cached_all_services

from port_ocean.context.event import event
from port_ocean.core.handlers import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        project_id, ref = _validate_project_scope(data)
        project = _get_project_from_cache(project_id)
        logger.info(f"Searching for file {pattern} in Project {project_id}, ref {ref}")

        file_path = pattern.replace(self.prefix, "")
        return (
            project.files.get(file_path=file_path, ref=ref).decode().decode("utf-8")
            if project
            else None
        )


class SearchEntityProcessor(JQEntityProcessor):
    prefix = SEARCH_PROPERTY_PREFIX
    separation_symbol = "&&"

    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        """
        Handles entity mapping for search:// pattern
        :param data: project data
        :param pattern: e.g. search://scope=blobs&&query=filename:port.yml
        :return: True if the search pattern matches, False otherwise
        """
        project_id, _ = _validate_project_scope(data)
        scope, query = self._parse_search_pattern(pattern)

        # assuming that the code is being called after event initialization and as part of the GitLab service
        # initialization
        project = _get_project_from_cache(project_id)
        logger.info(f"Searching for {query} in Project {project_id}, scope {scope}")

        match = None
        if project:
            match = bool(project.search(scope=scope, search=query))
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
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            entity_processor = SearchEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return entity_processor(self.context)._search(data, pattern)


class GitlabSelector(Selector):
    include_project_languages: bool | None = Field(
        alias="includeProjectLanguages", default=False
    )


class GitlabResourceConfig(ResourceConfig):
    selector: GitlabSelector


class GitlabPortAppConfig(PortAppConfig):
    spec_path: str | List[str] = Field(alias="specPath", default="**/port.yml")
    branch: str = "main"
    filter_owned_projects: bool | None = Field(
        alias="filterOwnedProjects", default=True
    )
    project_visibility_filter: str | None = Field(
        alias="projectVisibilityFilter", default=None
    )
    resources: list[GitlabResourceConfig] = Field(default_factory=list)


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


def _validate_project_scope(data: Dict[str, Any]) -> Tuple[int, str]:
    if (project_id := data.get("id")) and (ref := data.get("default_branch")):
        return project_id, ref
    raise ValueError("Project id and ref are required")
