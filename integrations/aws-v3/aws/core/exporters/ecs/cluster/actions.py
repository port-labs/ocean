from typing import Dict, Any, List, Type, Union
from aws.core.interfaces.action import (
    Action,
    BatchAction,
    ActionMap,
)
from loguru import logger


class ECSClusterDetailsAction(BatchAction):

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


class GetClusterPendingTasksAction(Action):

    async def _execute(self, cluster_arn: str) -> Dict[str, Any]:
        """Get up to 100 pending task ARNs for a cluster"""

        response = await self.client.list_tasks(  # type: ignore[attr-defined]
            cluster=cluster_arn, desiredStatus="PENDING", maxResults=100
        )

        task_arns = response["taskArns"]
        logger.info(f"Found {len(task_arns)} pending tasks for cluster {cluster_arn}")
        return {"pendingTaskArns": task_arns}


class ECSClusterActionsMap(ActionMap):
    defaults: List[Type[Union[Action, BatchAction]]] = [
        ECSClusterDetailsAction,
    ]

    options: List[Type[Union[Action, BatchAction]]] = [
        GetClusterPendingTasksAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Union[Action, BatchAction]]]:
        """Merge default actions with requested optional actions."""
        if not include:
            return self.defaults

        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
