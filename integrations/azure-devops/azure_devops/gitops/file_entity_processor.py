import asyncio
from typing import Any, Dict, List, Tuple, Type
from pydantic import BaseModel, Field
from port_ocean.core.handlers import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import Selector
from azure_devops.client.azure_devops_client import AzureDevopsClient

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


class AzureDevopsFileEntityProcessor(JQEntityProcessor):
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        client = AzureDevopsClient.create_from_ocean_config()
        repository_id, branch = parse_repository_payload(data)
        file_path = pattern.replace(FILE_PROPERTY_PREFIX, "")
        # Because of the current state of Ocean Entity processor this has to be sync.

        # TODO: make sure if making this function call sync if possible, it's currently not working.
        loop = asyncio.new_event_loop()
        file_raw_content = loop.run_until_complete(client.get_file_by_branch(file_path, repository_id, branch))
        loop.close()           
        # Wait for the file content to be fetched, if it's not done mean
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
    return repository_id, ref
