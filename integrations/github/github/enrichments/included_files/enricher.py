import asyncio
from typing import Any

from loguru import logger

from .fetcher import IncludedFileFetchKey, IncludedFilesFetcher
from .strategies import IncludedFilesStrategy
from .utils import IncludedFilesTarget
from .utils import resolve_included_file_path


class IncludedFilesEnricher:
    """Enriches raw entities with `__includedFiles` based on a strategy.

    The strategy decides:
    - which requested paths apply to each entity
    - how to build entity context (org/repo/branch/base_path)
    """

    def __init__(
        self,
        *,
        rest_client: Any,
        strategy: IncludedFilesStrategy,
    ) -> None:
        self._strategy = strategy
        self._fetcher = IncludedFilesFetcher(rest_client=rest_client)

    async def enrich_batch(
        self, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not entities:
            return entities

        logger.info(
            f"IncludedFilesEnricher: enriching {len(entities)} entities (strategy={type(self._strategy).__name__})"
        )

        planned: list[tuple[dict[str, Any], str, str, IncludedFileFetchKey]] = []
        for entity in entities:
            ctx = self._strategy.context_for(entity)

            plan_items = self._strategy.plan_items_for(entity, ctx)
            for item in plan_items:
                if not item.requested_path:
                    continue

                resolved = resolve_included_file_path(
                    requested_path=item.requested_path, base_path=item.base_path
                )
                key = IncludedFileFetchKey(
                    organization=ctx.organization,
                    repo_name=ctx.repo_name,
                    branch=ctx.branch,
                    file_path=resolved,
                )
                planned.append((entity, item.target, item.requested_path, key))

        if not planned:
            logger.info("IncludedFilesEnricher: no includedFiles planned for batch")
            return entities

        keys = [key for _, _, _, key in planned]
        unique_keys = set(keys)

        logger.info(
            f"IncludedFilesEnricher: {len(planned)} attachments "
            f"across {len(unique_keys)} unique files"
        )

        await self._fetch_all(keys)

        for entity, target, requested, key in planned:
            target_obj = (
                entity if target == IncludedFilesTarget.ENTITY else entity[target]
            )

            target_obj.setdefault("__includedFiles", {})
            target_obj["__includedFiles"][requested] = await self._fetcher.get(key)

        return entities

    async def _fetch_all(self, keys: list[IncludedFileFetchKey]) -> None:
        await asyncio.gather(*(self._fetcher.get(k) for k in keys))
