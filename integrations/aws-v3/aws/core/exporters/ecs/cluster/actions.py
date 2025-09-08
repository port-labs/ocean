from typing import Dict, Any, List, Type, cast
import asyncio

from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class DescribeClustersAction(Action):
    async def _execute(self, cluster_arns: List[str]) -> List[Dict[str, Any]]:
        if not cluster_arns:
            return []

        response = await self.client.describe_clusters(
            clusters=cluster_arns,
            include=["TAGS", "ATTACHMENTS", "SETTINGS", "CONFIGURATIONS", "STATISTICS"],
        )

        clusters = response["clusters"]
        results: List[Dict[str, Any]] = []
        for cluster in clusters:
            results.append(cluster)

        return results


class GetClusterPendingTasksAction(Action):
    async def _execute(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        pending_tasks_results = await asyncio.gather(
            *(self._fetch_pending_tasks(cluster) for cluster in clusters),
            return_exceptions=True,
        )
        for idx, pending_tasks_result in enumerate(pending_tasks_results):
            if isinstance(pending_tasks_result, Exception):
                cluster_name = clusters[idx].get("ClusterName", "unknown")
                logger.warning(
                    f"Error fetching pending tasks for cluster '{cluster_name}': {pending_tasks_result}"
                )
                results.append({"PendingTasks": []})
            else:
                results.append(cast(Dict[str, Any], pending_tasks_result))
        return results

    async def _fetch_pending_tasks(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cluster_name = cluster.get("ClusterName", "unknown")

            response = await self.client.list_tasks(
                cluster=cluster_name, desiredStatus="PENDING"
            )

            task_arns = response["taskArns"]

            # If there are pending tasks, get their details
            pending_tasks = []
            if task_arns:
                # Describe tasks to get detailed information
                describe_response = await self.client.describe_tasks(
                    cluster=cluster_name, tasks=task_arns
                )
                pending_tasks = describe_response.get("tasks", [])

            logger.info(
                f"Successfully fetched {len(pending_tasks)} pending tasks for cluster {cluster_name}"
            )
            return {"PendingTasks": pending_tasks}

        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ClusterNotFoundException":
                logger.info(
                    f"Cluster {cluster.get('ClusterName', 'unknown')} not found"
                )
                return {"PendingTasks": []}
            else:
                raise


class EcsClusterActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        DescribeClustersAction,
    ]
    options: List[Type[Action]] = [
        GetClusterPendingTasksAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
