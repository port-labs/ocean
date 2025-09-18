from typing import Dict, Any, List, Type

from aws.core.interfaces.action import Action, ActionMap


class DescribeClustersAction(Action):
    async def _execute(self, cluster_arns: List[str]) -> List[Dict[str, Any]]:
        if not cluster_arns:
            return []

        response = await self.client.describe_clusters(
            clusters=cluster_arns,
            include=["TAGS", "ATTACHMENTS", "SETTINGS", "CONFIGURATIONS", "STATISTICS"],
        )

        clusters = response["clusters"]
        return clusters


class EcsClusterActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        DescribeClustersAction,
    ]
    options: List[Type[Action]] = []
