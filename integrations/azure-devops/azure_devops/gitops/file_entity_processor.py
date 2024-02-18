from typing import Any, Dict, List, Tuple, Type
from pydantic import BaseModel, Field
from port_ocean.core.handlers import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import Selector
from azure_devops.client import AzureDevopsHTTPClient
from loguru import logger

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


class AzureDevopsFileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        client = AzureDevopsHTTPClient.create_from_ocean_config()
        repository_id, branch = parse_repository_payload(data)
        file_path = pattern.replace(self.prefix, "")
        # Because of the current state of Ocean Entitiy processor this has to be sync.
        file_raw_content = client.get_file_by_branch(file_path, repository_id, branch)
        return file_raw_content.decode() if file_raw_content else None


class GitManipulationHandler(JQEntityProcessor):
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = AzureDevopsFileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return entity_processor(self.context)._search(data, pattern)


class FoldersSelector(BaseModel):
    path: str
    repos: List[str] = Field(default_factory=list)
    branch: str | None = None


class GitSelector(Selector):
    folders: List[FoldersSelector] = Field(default_factory=list)


def parse_repository_payload(data: Dict[str, Any]) -> Tuple[str, str]:
    repository_id = data.get("id", "")
    ref = "/".join(
        data.get("defaultBranch", "").split("/")[2:]
    )  # Remove /refs/heads from ref to get branch
    if repository_id and ref:
        return repository_id, ref
    raise ValueError("Repository id and ref are required")
