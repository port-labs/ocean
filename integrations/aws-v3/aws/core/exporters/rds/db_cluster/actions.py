from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class DescribeDBClustersAction(Action[list[dict[str, Any]]]):
    """Pass-through action that returns raw cluster dicts from the paginator."""

    async def _execute(self, db_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return db_clusters


class ListTagsForResourceAction(Action[list[dict[str, Any]]]):
    """Fetches tags for RDS DB clusters."""

    async def _execute(self, db_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=db_clusters,
            operation_func=self._fetch_tags,
            get_resource_identifier=lambda c: c.get("DBClusterIdentifier", "unknown"),
            operation_name="DB cluster tags",
        )

    async def _fetch_tags(self, db_cluster: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.list_tags_for_resource(
            ResourceName=db_cluster["DBClusterArn"]
        )
        return {"TagList": response["TagList"]}


class RdsDbClusterActionsMap(ActionMap[list[dict[str, Any]]]):
    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        DescribeDBClustersAction,
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = [
        ListTagsForResourceAction,
    ]
