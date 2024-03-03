import asyncio
from typing import Any, Dict, Tuple, Type
from port_ocean.core.handlers import JQEntityProcessor
from azure_devops.client.azure_devops_client import AzureDevopsClient

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


class AzureDevopsFileEntityProcessor(JQEntityProcessor):
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        client = AzureDevopsClient.create_from_ocean_config()
        repository_id, branch = parse_repository_payload(data)
        file_path = pattern.replace(FILE_PROPERTY_PREFIX, "")
        file_raw_content = asyncio.get_running_loop().run_until_complete(
            client.get_file_by_branch(file_path, repository_id, branch)
        )
        return file_raw_content.decode() if file_raw_content else None


class GitManipulationHandler(JQEntityProcessor):
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = AzureDevopsFileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return entity_processor(self.context)._search(data, pattern)


def parse_repository_payload(data: Dict[str, Any]) -> Tuple[str, str]:
    repository_id = data.get("id", "")
    ref = "/".join(
        data.get("defaultBranch", "").split("/")[2:]
    )  # Remove /refs/heads from ref to get branch
    return repository_id, ref
