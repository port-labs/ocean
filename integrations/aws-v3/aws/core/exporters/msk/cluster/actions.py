from typing import Any, List, Type

from aws.core.interfaces.action import Action, ActionMap


class ListClustersAction(Action[list[dict[str, Any]]]):
    """List MSK clusters as a pass-through action."""

    async def _execute(self, clusters: List[dict[str, Any]]) -> List[dict[str, Any]]:
        """Return MSK clusters as-is since list_clusters returns complete data."""
        return clusters


class MskClusterActionsMap(ActionMap):
    """Groups all actions for MSK cluster resources."""

    defaults: List[Type[Action]] = [ListClustersAction]
    options: List[Type[Action]] = []
