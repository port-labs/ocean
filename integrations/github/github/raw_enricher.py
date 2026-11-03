import os
from typing import Any, Optional

from loguru import logger
from port_ocean.core.handlers import MappingRefRawEnricher
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import collect_mapping_refs

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.options import FileContentOptions


class GithubRawEnricher(MappingRefRawEnricher):
    """Resolves `file://` mapping values against the item's repository."""

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

    async def _get_file_content(
        self,
        organization: str,
        repo_name: str,
        file_path: str,
        branch: Optional[str] = None,
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""

        rest_client = await create_github_client_for_org(organization)
        exporter = RestFileExporter(rest_client)

        file_content_response = await exporter.get_resource(
            FileContentOptions(
                organization=organization,
                repo_name=repo_name,
                file_path=file_path,
                branch=branch,
            )
        )
        if not file_content_response:
            return None
        decoded_content = file_content_response["content"]
        if not decoded_content:
            logger.info(f"File too large, size - {file_content_response['size']} bytes")
            return None

        logger.info(
            f"File content fetched, size - {file_content_response['size']} bytes"
        )
        return decoded_content

    async def resolve_file_ref(self, item: RAW_ITEM, path: str) -> Any:
        """Return the content of `path` in the item's repository.

        For monorepo items the item holds "repository", "branch" and "metadata.path", and `path`
        is relative to the folder of `metadata.path`. Otherwise the item is the repository itself
        and the default branch is used.
        """
        repo_data = item.get("repository", item)
        is_monorepo = "repository" in item

        repo_name = repo_data["name"]
        organization = repo_data["owner"]["login"]
        ref = item["branch"] if is_monorepo else repo_data.get("default_branch")

        file_path = (
            os.path.join(os.path.dirname(item["metadata"]["path"]), path).replace(
                os.sep, "/"
            )
            if is_monorepo
            else path
        )

        logger.info(
            f"Searching for file {file_path} in Repository {repo_name}, ref {ref}"
        )

        return await self._get_file_content(organization, repo_name, file_path, ref)
