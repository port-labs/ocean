from typing import Dict, Any, List, Type
from aws.core.interfaces.action import (
    Action,
    DataAction,
    APIAction,
    BatchAPIAction,
    ActionMap,
)
from loguru import logger
from aws.core.helpers.utils import extract_resource_name_from_arn


class ECSClusterDetailsAction(BatchAPIAction):

    async def _execute(self, cluster_arn: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "Single execution not supported for ECSClusterDetailsAction. Use execute_batch instead."
        )

    async def _execute_batch(self, cluster_arns: List[str]) -> List[Dict[str, Any]]:
        if not cluster_arns:
            return []

        response = await self.client.describe_clusters(  # type: ignore[attr-defined]
            clusters=cluster_arns,
            include=["TAGS", "SETTINGS", "CONFIGURATIONS", "STATISTICS", "ATTACHMENTS"],
        )

        clusters = response["clusters"]
        logger.info(
            f"Successfully fetched ECS cluster details for {len(clusters)} clusters"
        )
        return clusters


class GetClusterPendingTasksAction(APIAction):

    async def _execute(self, cluster_arn: str) -> Dict[str, Any]:
        """Get up to 100 pending task ARNs for a cluster"""
        cluster_name = extract_resource_name_from_arn(cluster_arn)

        response = await self.client.list_tasks(  # type: ignore[attr-defined]
            cluster=cluster_arn, desiredStatus="PENDING", maxResults=100
        )

        task_arns = response["taskArns"]
        logger.info(f"Found {len(task_arns)} pending tasks for cluster {cluster_name}")
        return {"pendingTaskArns": task_arns}


class ECSClusterActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        ECSClusterDetailsAction,
    ]

    options: List[Type[Action]] = [
        GetClusterPendingTasksAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        """Merge default actions with requested optional actions."""
        if not include:
            return self.defaults

        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
