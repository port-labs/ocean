from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DescribeDBClustersAction(Action):
    """Pass-through action that returns raw cluster dicts from the paginator."""

    async def _execute(self, db_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return db_clusters


class ListTagsForResourceAction(Action):
    """Fetches tags for RDS DB clusters."""

    async def _execute(self, db_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tag_results = await asyncio.gather(
            *(self._fetch_tags(cluster) for cluster in db_clusters),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, tag_result in enumerate(tag_results):
            if isinstance(tag_result, Exception):
                cluster_id = db_clusters[idx].get("DBClusterIdentifier", "unknown")
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for DB cluster '{cluster_id}': {tag_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching tags for DB cluster '{cluster_id}': {tag_result}"
                    )
                    raise tag_result
            results.extend(cast(list[dict[str, Any]], tag_result))
        logger.info(f"Successfully fetched tags for {len(results)} DB clusters")
        return results

    async def _fetch_tags(self, db_cluster: dict[str, Any]) -> list[dict[str, Any]]:
        response = await self.client.list_tags_for_resource(
            ResourceName=db_cluster["DBClusterArn"]
        )
        return [{"Tags": response["TagList"]}]


class RdsDbClusterActionsMap(ActionMap):
    defaults: list[Type[Action]] = [
        DescribeDBClustersAction,
    ]
    options: list[Type[Action]] = [
        ListTagsForResourceAction,
    ]
