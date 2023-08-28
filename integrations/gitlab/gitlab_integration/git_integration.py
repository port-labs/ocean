import typing
from functools import lru_cache
from typing import Dict, Any, Tuple, List

from gitlab_integration.core.entities import (
    FILE_PROPERTY_PREFIX,
    SEARCH_PROPERTY_PREFIX,
)
from gitlab_integration.gitlab_service import PROJECTS_CACHE_KEY
from loguru import logger
from pydantic import Field
from gitlab.v4.objects import Project

from port_ocean.context.event import event
from port_ocean.core.handlers import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        project_id, ref = self._validate_project_scope(data)
        logger.info(f"Searching for file {pattern} in Project {project_id}, ref {ref}")
        # relying on that the code is being called after event initialization and as part of the GitLab service
        # initialization
        project_client: Project | None = event.attributes["PROJECTS_CACHE_KEY"][
            project_id
        ]

        file_path = pattern.replace(self.prefix, "")
        return (
            self._get_file_content(project_client, file_path, ref)
            if project_client
            else None
        )

    @lru_cache()
    def _get_file_content(
        self, project_client: Project, file_path: str, ref: str
    ) -> str:
        return (
            project_client.files.get(file_path=file_path, ref=ref)
            .decode()
            .decode("utf-8")
        )

    @staticmethod
    def _validate_project_scope(data: Dict[str, Any]) -> Tuple[int, str]:
        if (project_id := data.get("id")) and (ref := data.get("default_branch")):
            return project_id, ref
        raise ValueError("Project id and ref are required")


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
        project_id, _ = self._validate_project_scope(data)
        scope, query = self._parse_search_pattern(pattern)
        logger.info(f"Searching for {query} in Project {project_id}, scope {scope}")
        project: Project | None = event.attributes[PROJECTS_CACHE_KEY][project_id]

        match = False
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
                f"Search pattern {pattern} does not contain separation symbol {self.separation_symbol}"
            )
        # handle case when the query contains the separation symbol
        elif len(pattern.split(self.separation_symbol)) > 2:
            splitted_patten = pattern.split(self.separation_symbol)
            scope = splitted_patten[0]
            query = self.separation_symbol.join(splitted_patten[1:])
        # default case
        else:
            scope, query = pattern.split(self.separation_symbol)

        # return the actual scope and query values
        # e.g. scope=blobs -> blobs, query=filename:port.yml -> filename:port.yml
        return scope.split("=")[1], "=".join(query.split("=")[1:])

    @staticmethod
    def _validate_project_scope(data: Dict[str, Any]) -> Tuple[int, str]:
        if (project_id := data.get("id")) and (ref := data.get("default_branch")):
            return project_id, ref
        raise ValueError("Project id and ref are required")


def get_entity_processor_by_pattern(pattern: str) -> typing.Type[JQEntityProcessor]:
    if pattern.startswith(FILE_PROPERTY_PREFIX):
        return FileEntityProcessor
    elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
        return SearchEntityProcessor
    else:
        return JQEntityProcessor


class GitManipulationHandler(JQEntityProcessor):
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor = get_entity_processor_by_pattern(pattern)
        return entity_processor(self.context)._search(data, pattern)


class GitlabPortAppConfig(PortAppConfig):
    spec_path: str | List[str] = Field(alias="specPath", default="**/port.yml")
    branch: str = "main"
