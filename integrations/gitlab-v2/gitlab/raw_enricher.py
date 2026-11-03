import asyncio
from typing import Any

from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.core.handlers import MappingRefRawEnricher
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import collect_mapping_refs

from gitlab.clients.client_factory import create_gitlab_client
from gitlab.entity_processors.utils import parse_search_string

MAX_SEARCH_REQUESTS_PER_SECOND = 2
_search_rate_limiter = AsyncLimiter(MAX_SEARCH_REQUESTS_PER_SECOND, 1)
_search_semaphore = asyncio.Semaphore(2)


def _project_path(item: RAW_ITEM) -> str:
    project_path = item.get("path_with_namespace") or item.get("repo", {}).get(
        "path_with_namespace"
    )
    if not project_path:
        logger.error("No project path found in data")
        raise ValueError("No project path found in data")
    return project_path


class GitlabRawEnricher(MappingRefRawEnricher):
    """Resolves `file://` and `search://` mapping values against the item's project."""

    async def enrich(
        self, resource: ResourceConfig, items: list[RAW_ITEM]
    ) -> list[RAW_ITEM]:
        refs = collect_mapping_refs(resource.port.entity.mappings.dict())
        for path in refs.files:
            logger.warning(
                f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: 'file://{path}'. "
                f"Use the 'includedFiles' selector instead. Example: "
                f"selector.includedFiles: ['{path}'] "
                f'and mapping: .__includedFiles["{path}"]'
            )
        for query in refs.searches:
            logger.warning(
                f"DEPRECATION: Using 'search://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: 'search://{query}'. "
                f"Use the 'searchQueries' selector instead. Example: "
                f"selector.searchQueries: [{{name: '<queryName>', scope: '<scope>', query: '<query>'}}] "
                f'Then map to .__searchQueries["<queryName>"]'
            )
        return await super().enrich(resource, items)

    async def resolve_file_ref(self, item: RAW_ITEM, path: str) -> Any:
        project_path = _project_path(item)
        ref = item.get("default_branch") or item.get("repo", {}).get("default_branch")
        if not ref:
            logger.error("No branch reference found in data")
            raise ValueError("No branch reference found in data")

        logger.info(
            f"Fetching content for file: '{path}' in project: '{project_path}' (branch: '{ref}')"
        )
        return await create_gitlab_client().get_file_content(project_path, path, ref)

    async def resolve_search_ref(self, item: RAW_ITEM, query: str) -> Any:
        project_path = _project_path(item)
        scope, search_query = parse_search_string(query.strip())
        async with _search_semaphore:
            async with _search_rate_limiter:
                logger.info(
                    f"Checking for file existence using query: '{search_query}' in scope: '{scope}' for project: '{project_path}'"
                )
                return await create_gitlab_client().file_exists(
                    project_path, scope, search_query
                )
