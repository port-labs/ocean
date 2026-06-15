from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap


class ListMskServerlessClustersAction(Action[list[dict[str, Any]]]):
    """Pass-through: list_clusters_v2 returns full ClusterInfo objects."""

    async def _execute(self, clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return clusters


class MskServerlessClusterActionsMap(ActionMap[list[dict[str, Any]]]):
    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        ListMskServerlessClustersAction
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = []
