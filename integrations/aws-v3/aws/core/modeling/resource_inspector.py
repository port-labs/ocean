from typing import List, Dict, Any, Callable, Optional, cast
from loguru import logger
import asyncio
from aws.core.interfaces.action import (
    Action,
    BatchAction,
    SingleActionMap,
    BatchActionMap,
)
from aws.core.modeling.resource_builder import ResourceBuilder, PropertiesData
from aws.core.modeling.resource_models import ResourceModel


class SingleResourceInspector[ResourceModelT: ResourceModel[Any]]:
    """
    Inspects single AWS resources by executing actions and building resource models.
    Uses SingleActionMap which guarantees only Action types for single resource operations.
    """

    def __init__(
        self,
        client: Any,
        actions_map: SingleActionMap,
        model_factory: Callable[[], ResourceModelT],
        account_id: str,
        region: Optional[str] = None,
        max_concurrent_requests: int = 15,
    ) -> None:
        """
        Initialize the SingleResourceInspector.

        Args:
            client: The AWS client instance to be used by actions.
            actions_map: The map of available actions (SingleActionMap with Action types only).
            model_factory: A callable that returns a new instance of the resource model.
            region: The AWS region for this resource (optional).
            account_id: The AWS account ID for this resource.
        """
        self.client = client
        self.actions_map = actions_map
        self.model_factory = model_factory
        self.region = region
        self.account_id = account_id

    async def inspect(self, identifier: str, include: List[str]) -> ResourceModelT:
        """Inspect a single resource using Action types only."""
        if not identifier:
            return self.model_factory()

        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]

        # Execute actions directly - all actions are guaranteed to be Action types
        results = await asyncio.gather(
            *(action.execute(identifier) for action in actions)
        )

        return self._build_model(results)

    def _build_model(self, identifier_results: List[Dict[str, Any]]) -> ResourceModelT:
        """Build a resource model from identifier results using ResourceBuilder."""
        builder: ResourceBuilder[ResourceModelT, Any] = ResourceBuilder(
            self.model_factory(), self.region or "", self.account_id or ""
        )

        properties_data: List[PropertiesData] = [
            cast(PropertiesData, result) for result in identifier_results
        ]
        builder.with_properties(properties_data)

        return builder.build()


class BatchResourceInspector[ResourceModelT: ResourceModel[Any]]:
    """
    Inspects multiple AWS resources by executing actions and building resource models.
    Uses BatchActionMap which guarantees only BatchAction types for batch operations.
    """

    def __init__(
        self,
        client: Any,
        actions_map: BatchActionMap,
        model_factory: Callable[[], ResourceModelT],
        region: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the BatchResourceInspector.

        Args:
            client: The AWS client instance to be used by actions.
            actions_map: The map of available actions (BatchActionMap with BatchAction types only).
            model_factory: A callable that returns a new instance of the resource model.
            region: The AWS region for this resource (optional).
            account_id: The AWS account ID for this resource (optional).
        """
        self.client = client
        self.actions_map = actions_map
        self.model_factory = model_factory
        self.region = region
        self.account_id = account_id

    async def inspect_batch(
        self, identifiers: List[str], include: List[str]
    ) -> List[ResourceModelT]:
        """Inspect multiple resources using BatchAction types only."""
        if not identifiers:
            return []

        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]

        results = await asyncio.gather(
            *(action.execute_batch(identifiers) for action in actions)
        )

        return self._build_models(results)

    def _build_models(
        self, action_results: List[List[Dict[str, Any]]]
    ) -> List[ResourceModelT]:
        """
        Build resource models from action results.
        Args:
            action_results: List of result lists, one per action.
                            Each inner list contains results for each identifier.
        Returns:
            List of built resource models, one per identifier.
        """
        valid_results = [result for result in action_results if result]
        if not valid_results:
            return []

        return [
            self._build_model(identifier_results)
            for identifier_results in zip(*valid_results)
        ]

    def _build_model(self, identifier_results: List[Dict[str, Any]]) -> ResourceModelT:
        """Build a resource model from identifier results using ResourceBuilder."""
        builder: ResourceBuilder[ResourceModelT, Any] = ResourceBuilder(
            self.model_factory(), account_id=self.account_id, region=self.region
        )

        properties_data: List[PropertiesData] = [
            cast(PropertiesData, result) for result in identifier_results
        ]
        builder.with_properties(properties_data)

        return builder.build()
