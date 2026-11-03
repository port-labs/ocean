from typing import Any, Dict, Optional, Tuple

from loguru import logger
from port_ocean.core.handlers import MappingRefRawEnricher
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import collect_mapping_refs

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.misc import ORG_URL_FIELD, extract_branch_name_from_ref


class AzureDevopsRawEnricher(MappingRefRawEnricher):
    """Resolves `file://` mapping values against the item's repository and branch."""

    async def enrich(
        self, resource: ResourceConfig, items: list[RAW_ITEM]
    ) -> list[RAW_ITEM]:
        for path in collect_mapping_refs(resource.port.entity.mappings.dict()).files:
            logger.warning(
                f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: 'file://{path}'. "
                f"Use the 'includedFiles' selector instead. Example: "
                f"selector.includedFiles: ['{path}'] "
                f'and mapping: .__includedFiles["{path}"]'
            )
        return await super().enrich(resource, items)

    def _get_client_for_entity(
        self, data: Dict[str, Any]
    ) -> Optional[AzureDevopsClient]:
        """Resolve the per-org client from __organizationUrl on the item."""
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

    async def resolve_file_ref(self, item: RAW_ITEM, path: str) -> Any:
        client = self._get_client_for_entity(item)
        if not client:
            return None
        repository_id, branch = parse_repository_payload(item)
        file_raw_content = await client.get_file_by_branch(path, repository_id, branch)
        return file_raw_content.decode() if file_raw_content else None


def parse_repository_payload(data: Dict[str, Any]) -> Tuple[str, str]:
    repository_id = data.get("id") or data.get("__repository", {}).get("id")
    branch = extract_branch_name_from_ref(
        data.get("defaultBranch") or data.get("__branch", "")
    )
    return repository_id, branch
