from typing import Any, Tuple

from loguru import logger
from port_ocean.core.handlers import MappingRefRawEnricher
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import collect_mapping_refs

from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.git_integration import (
    _get_project_from_cache,
    _validate_project_scope,
)

SEARCH_SEPARATION_SYMBOL = "&&"


def parse_search_query(query: str) -> Tuple[str, str]:
    """
    :param query: e.g. scope=blobs&&query=filename:port.yml
    :return: scope, search_pattern
    """
    if len(query.split(SEARCH_SEPARATION_SYMBOL)) == 1:
        raise ValueError(
            f"Search pattern {query} does not match the expected format: search://scope=<scope>&&query=<query>"
        )
    scope, search = query.split(SEARCH_SEPARATION_SYMBOL, 1)

    # e.g. scope=blobs -> blobs, query=filename:port.yml -> filename:port.yml
    return scope.split("=")[1], "=".join(search.split("=")[1:])


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
        project_id, ref, base_path = _validate_project_scope(item)
        project = _get_project_from_cache(project_id)

        file_path = f"{base_path}/{path}" if base_path else path
        if not project:
            return None
        logger.info(
            f"Searching for file {file_path} in Project {project_id}: {project.path_with_namespace}, ref {ref}"
        )
        res = await AsyncFetcher.fetch_single(project.files.get, file_path, ref)
        return res.decode().decode("utf-8")

    async def resolve_search_ref(self, item: RAW_ITEM, query: str) -> Any:
        """
        :param query: e.g. scope=blobs&&query=filename:port.yml
        :return: True if the search matches, False otherwise
        """
        project_id, _, base_path = _validate_project_scope(item)
        scope, search = parse_search_query(query)

        project = _get_project_from_cache(project_id)
        if not project:
            return None
        base_path_message = f" in base path {base_path}" if base_path else ""
        logger.info(
            f"Searching {search} {base_path_message} in Project {project_id}: {project.path_with_namespace}, "
            f"scope {scope}"
        )
        # Scoping a blob search to the exported folder avoids searching the whole project
        # when a folder is exported as a monorepo.
        if scope == "blobs" and base_path and "path:" not in search:
            search = f"{search} path:{base_path}"
        results = await AsyncFetcher.fetch_single(project.search, scope, search)  # type: ignore
        return bool(results)
