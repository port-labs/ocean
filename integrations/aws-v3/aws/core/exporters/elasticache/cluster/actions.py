from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DescribeCacheClustersAction(Action):
    """Pass-through action that returns the raw cluster data."""

    async def _execute(
        self, cache_clusters: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return cache_clusters


class ListTagsForResourceAction(Action):
    """Fetches tags for ElastiCache clusters."""

    async def _execute(
        self, cache_clusters: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        tag_results = await asyncio.gather(
            *(self._fetch_tags(cluster) for cluster in cache_clusters),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        success_count = 0
        for idx, tag_result in enumerate(tag_results):
            if isinstance(tag_result, Exception):
                cluster_id = cache_clusters[idx].get("CacheClusterId", "unknown")
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for cache cluster '{cluster_id}': {tag_result}"
                    )
                    results.append({})
                    continue
                else:
                    logger.error(
                        f"Error fetching tags for cache cluster '{cluster_id}': {tag_result}"
                    )
                    raise tag_result
            results.extend(cast(list[dict[str, Any]], tag_result))
            success_count += 1
        logger.info(f"Successfully fetched tags for {success_count} cache clusters")
        return results

    async def _fetch_tags(self, cache_cluster: dict[str, Any]) -> list[dict[str, Any]]:
        response = await self.client.list_tags_for_resource(
            ResourceName=cache_cluster["ARN"]
        )
        return [{"TagList": response.get("TagList", [])}]


class ElastiCacheClusterActionsMap(ActionMap):
    defaults: list[Type[Action]] = [
        DescribeCacheClustersAction,
    ]
    options: list[Type[Action]] = [
        ListTagsForResourceAction,
    ]
