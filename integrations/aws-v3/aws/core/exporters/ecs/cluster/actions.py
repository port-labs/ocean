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


class EcsClusterActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        DescribeClustersAction,
    ]
    options: List[Type[Action]] = []
