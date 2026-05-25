from typing import Any, Dict, Optional, Tuple

from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.misc import ORG_URL_FIELD, extract_branch_name_from_ref

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


class GitManipulationHandler(JQEntityProcessor):
    async def _search(
        self, data: Dict[str, Any], pattern: str, field: str | None = None
    ) -> Any:
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            logger.warning(
                f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: '{pattern}'. "
                f"Use the 'includedFiles' selector instead. Example: "
                f"selector.includedFiles: ['{pattern[len(FILE_PROPERTY_PREFIX):]}'] "
                f'and mapping: .__includedFiles["{pattern[len(FILE_PROPERTY_PREFIX):]}"]'
            )
            return await self._search_by_file(data, pattern)

        return await super()._search(data, pattern, field)

    def _get_client_for_entity(self, data: Dict[str, Any]) -> Optional[AzureDevopsClient]:
        """Resolve the per-org client from __organizationUrl on the entity."""
        org_url: Optional[str] = data.get(ORG_URL_FIELD)
        if not org_url:
            logger.warning("Skipping file search: entity has no __organizationUrl")
            return None
        manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
        client = manager.get_client_for_org(org_url)
        if not client:
            logger.warning(
                f"Skipping file search: no configured client for org '{org_url}'"
            )
        return client

    async def _search_by_file(self, data: Dict[str, Any], pattern: str) -> Any:
        client = self._get_client_for_entity(data)
        if not client:
            return None
        repository_id, branch = parse_repository_payload(data)
        file_path = pattern.replace(FILE_PROPERTY_PREFIX, "")
        file_raw_content = await client.get_file_by_branch(
            file_path, repository_id, branch
        )
        return file_raw_content.decode() if file_raw_content else None


def parse_repository_payload(data: Dict[str, Any]) -> Tuple[str, str]:
    repository_id = data.get("id") or data.get("__repository", {}).get("id")
    branch = extract_branch_name_from_ref(
        data.get("defaultBranch") or data.get("__branch", "")
    )
    return repository_id, branch
