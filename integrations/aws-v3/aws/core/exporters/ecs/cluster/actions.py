from typing import Dict, Any, List, Type
from aws.core.interfaces.action import IAction, IActionMap, IBatchAction
from loguru import logger
from aws.core.helpers.utils import extract_resource_name_from_arn


class ECSClusterDetailsAction(IBatchAction):
    """Single action that handles all ECS cluster details in one API call"""

    async def _execute_batch(self, cluster_arns: List[str]) -> List[Dict[str, Any]]:
        """Execute describe_clusters for multiple clusters in a single API call"""
        if not cluster_arns:
            return []

        response = await self.client.describe_clusters(
            clusters=cluster_arns,
            include=["TAGS", "SETTINGS", "CONFIGURATIONS", "STATISTICS", "ATTACHMENTS"],
        )

        clusters = response["clusters"]
        logger.info(
            f"Successfully fetched ECS cluster details for {len(clusters)} clusters"
        )
        return clusters


class GetClusterPendingTasksAction(IAction):
    """Action to get pending task ARNs for a cluster"""

    async def _execute(self, cluster_arn: str) -> Dict[str, Any]:
        """Get up to 100 pending task ARNs for a cluster"""
        cluster_name = extract_resource_name_from_arn(cluster_arn)

        response = await self.client.list_tasks(
            cluster=cluster_arn, desiredStatus="PENDING", maxResults=100
        )

        task_arns = response["taskArns"]
        logger.info(f"Found {len(task_arns)} pending tasks for cluster {cluster_name}")
        return {"pendingTaskArns": task_arns}


class ECSClusterActionsMap(IActionMap):
    defaults: List[Type[IAction]] = [
        ECSClusterDetailsAction,
    ]
    optional: List[Type[IAction]] = [
        GetClusterPendingTasksAction,
    ]

    def merge(self, include: List[str]) -> List[Type[IAction]]:
        return self.defaults + [
            action for action in self.optional if action.__name__ in include
        ]
