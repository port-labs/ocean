from typing import Dict, Any, List, Type, cast
import asyncio

from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class DescribeClustersAction(Action):
    async def _execute(self, cluster_arns: List[str]) -> List[Dict[str, Any]]:
        if not cluster_arns:
            return []
        
        # Get detailed cluster information
        response = await self.client.describe_clusters(
            clusters=cluster_arns, include=["TAGS"]
        )
        
        clusters = response["clusters"]
        results: List[Dict[str, Any]] = []
        for cluster in clusters:
            data = {
                "ClusterName": cluster["clusterName"],
                "CapacityProviders": cluster.get("capacityProviders", []),
                "ClusterSettings": cluster.get("settings", []),
                "Configuration": cluster.get("configuration"),
                "DefaultCapacityProviderStrategy": cluster.get("defaultCapacityProviderStrategy", []),
                "ServiceConnectDefaults": cluster.get("serviceConnectDefaults"),
                "Tags": cluster.get("tags", []),
                
                "Status": cluster.get("status"),
                "RunningTasksCount": cluster.get("runningTasksCount", 0),
                "ActiveServicesCount": cluster.get("activeServicesCount", 0),
                "PendingTasksCount": cluster.get("pendingTasksCount", 0),
                "RegisteredContainerInstancesCount": cluster.get("registeredContainerInstancesCount", 0),
                "Arn": cluster["clusterArn"],
            }
            results.append(data)
        
        return results


class GetClusterTagsAction(Action):
    async def _execute(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        tagging_results = await asyncio.gather(
            *(self._fetch_tagging(cluster) for cluster in clusters), return_exceptions=True
        )
        for idx, tagging_result in enumerate(tagging_results):
            if isinstance(tagging_result, Exception):
                cluster_name = clusters[idx].get("clusterName", "unknown")
                logger.warning(
                    f"Error fetching cluster tagging for cluster '{cluster_name}': {tagging_result}"
                )
                results.append({"Tags": []})
            else:
                results.append(cast(Dict[str, Any], tagging_result))
        return results

    async def _fetch_tagging(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_tags_for_resource(
                resourceArn=cluster["Arn"]
            )
            logger.info(
                f"Successfully fetched cluster tagging for cluster {cluster['Title']}"
            )
            return {"Tags": response.get("tags", [])}
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                logger.info(f"No tags found for cluster {cluster['Title']}")
                return {"Tags": []}
            else:
                raise


class EcsClusterActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        DescribeClustersAction,
    ]
    options: List[Type[Action]] = [
        GetClusterTagsAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
