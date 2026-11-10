import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import (
    INCLUDED_FILES_KEY,
    SEARCH_RESULTS_KEY,
    collect_mapping_refs,
)

if TYPE_CHECKING:
    from port_ocean.context.ocean import PortOceanContext


def _warn_deprecated_refs(files: set[str], searches: set[str]) -> None:
    for path in sorted(files):
        logger.warning(
            f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
            f"Pattern: 'file://{path}'. "
            f"Use the 'includedFiles' selector instead. Example: "
            f"selector.includedFiles: ['{path}'] "
            f'and mapping: .__includedFiles["{path}"]'
        )
    for query in sorted(searches):
        logger.warning(
            f"DEPRECATION: Using 'search://' prefix in mappings is deprecated and will be removed in a future version. "
            f"Pattern: 'search://{query}'. "
            f"Use the 'searchQueries' selector instead. Example: "
            f"selector.searchQueries: [{{name: '<queryName>', scope: '<scope>', query: '<query>'}}] "
            f'Then map to .__searchQueries["<queryName>"]'
        )


class BaseRawEnricher:
    """Attaches data that a resource's mapping needs to each raw item before it is sent to the
    data-source-processor, which evaluates mappings with plain jq and cannot fetch anything.
    """

    def __init__(self, context: "PortOceanContext") -> None:
        self.context = context

    async def enrich(
        self, resource: ResourceConfig, items: list[RAW_ITEM]
    ) -> list[RAW_ITEM]:
        return items


class MappingRefRawEnricher(BaseRawEnricher):
    """Keeps the deprecated `file://` and `search://` mapping values working.

    Each value is resolved per raw item and stored under `__includedFiles[path]` /
    `__search[query]`, which is what the mapping sent to the data-source-processor reads after
    `rewrite_mapping_refs`. Every use logs a deprecation warning pointing to the
    `includedFiles` / `searchQueries` selectors that replace them.
    """

    async def resolve_file_ref(self, item: RAW_ITEM, path: str) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__} does not support file:// mappings"
        )

    async def resolve_search_ref(self, item: RAW_ITEM, query: str) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__} does not support search:// mappings"
        )

    async def enrich(
        self, resource: ResourceConfig, items: list[RAW_ITEM]
    ) -> list[RAW_ITEM]:
        refs = collect_mapping_refs(resource.port.entity.mappings.dict())
        if not refs:
            return items
        _warn_deprecated_refs(refs.files, refs.searches)
        logger.info(
            "Resolving mapping references for raw items",
            kind=resource.kind,
            files=sorted(refs.files),
            searches=sorted(refs.searches),
            items=len(items),
        )
        await asyncio.gather(
            *(self._enrich_item(item, refs.files, refs.searches) for item in items)
        )
        return items

    async def _enrich_item(
        self, item: RAW_ITEM, files: set[str], searches: set[str]
    ) -> None:
        if files:
            included_files = item.setdefault(INCLUDED_FILES_KEY, {})
            for path in files:
                if path not in included_files:
                    included_files[path] = await self._resolve_safely(
                        self.resolve_file_ref, item, path
                    )
        if not searches:
            return
        search_results = item.setdefault(SEARCH_RESULTS_KEY, {})
        for query in searches:
            if query not in search_results:
                search_results[query] = await self._resolve_safely(
                    self.resolve_search_ref, item, query
                )

    @staticmethod
    async def _resolve_safely(resolver: Any, item: RAW_ITEM, ref: str) -> Any:
        try:
            return await resolver(item, ref)
        except NotImplementedError:
            raise
        except Exception as error:
            logger.warning(
                f"Failed to resolve mapping reference '{ref}', mapping it as null: {error}"
            )
            return None
