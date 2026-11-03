from typing import Any, Optional

from httpx import HTTPError
from loguru import logger
from port_ocean.core.handlers import MappingRefRawEnricher
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import collect_mapping_refs

from initialize_client import init_client


class BitbucketRawEnricher(MappingRefRawEnricher):
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
        self, repo_slug: str, ref: str, file_path: str
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""
        try:
            bitbucket_client = init_client()
            content = await bitbucket_client.get_repository_files(
                repo_slug, ref, file_path
            )
            if content is None:
                logger.warning(f"Resolving {file_path} in {repo_slug} to null")
            return content
        except HTTPError as e:
            logger.error(
                f"Failed to get file content for {file_path} in repository {repo_slug} in branch {ref}: {e}"
            )
            return None

    async def resolve_file_ref(self, item: RAW_ITEM, path: str) -> Any:
        """Return the content of `path` in the item's repository.

        For monorepo items the item holds "repo" and "folder", and `path` is relative to the
        folder at its commit. Otherwise the item is the repository itself and the main branch
        is used.
        """
        repo_data = item.get("repo", item)
        repo_slug = repo_data.get("name", "").replace(" ", "-")
        default_branch = (
            repo_data.get("mainbranch", {}).get("name", "main").replace(" ", "-")
        )

        if current_directory_path := item.get("folder", {}).get("path", ""):
            file_path = f"{current_directory_path}/{path}"
            ref = item.get("folder", {}).get("commit", {}).get("hash", default_branch)
        else:
            file_path = path
            if not default_branch:
                logger.info(
                    f"No default branch found for repository {repo_slug} and file path {file_path}"
                )
                return None
            ref = default_branch

        if not repo_slug:
            logger.info(
                f"No repository slug found for branch {ref} and file path {file_path}"
            )
            return None

        logger.info(
            f"Searching for file {file_path} in Repository {repo_slug}, ref {ref}"
        )
        return await self._get_file_content(repo_slug, ref, file_path)
