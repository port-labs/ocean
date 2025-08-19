from typing import List, Dict, Any, Callable, Optional
from loguru import logger
import asyncio
from aws.core.interfaces.action import Action, ActionMap, BatchAPIAction
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ResourceModel


class ResourceInspector[ResourceModelT: ResourceModel[Any]]:
    """
    Inspects AWS resources by executing actions and building resource models.

    Provides a simple interface to execute multiple actions for resource identifiers
    and aggregate their results into strongly-typed resource models.
    """

    def __init__(
        self,
        client: Any,
        actions_map: ActionMap,
        model_factory: Callable[[], ResourceModelT],
        region: Optional[str] = None,
        account_id: Optional[str] = None,
        max_concurrent_requests: int = 15,
    ) -> None:
        """
        Initialize the ResourceInspector.

        Args:
            client: The AWS client instance to be used by actions.
            actions_map: The map of available actions for the resource.
            model_factory: A callable that returns a new instance of the resource model.
            region: The AWS region for this resource (optional).
            account_id: The AWS account ID for this resource (optional).
        """
        self.client = client
        self.actions_map = actions_map
        self.model_factory = model_factory
        self.region = region
        self.account_id = account_id
        self.max_concurrent_requests = max_concurrent_requests

    async def inspect(self, identifier: str, include: List[str]) -> ResourceModelT:
        """Inspect a single resource."""
        if not identifier:
            return self.model_factory()

        # Execute actions and build models
        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]

        results = await asyncio.gather(
            *(self._run_action(action, [identifier]) for action in actions)
        )

        models = self._build_models(results)
        return models[0] if models else self.model_factory()

    async def inspect_batch(
        self, identifiers: List[str], include: List[str]
    ) -> List[ResourceModelT]:
        """Inspect multiple resources."""
        if not identifiers:
            return []

        # Execute actions and build models
        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]

        results = await asyncio.gather(
            *(self._run_action(action, identifiers) for action in actions)
        )

        return self._build_models(results)

    async def _run_action(
        self, action: Action, identifiers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Execute a single action for the given identifiers.

        Args:
            action: The action instance to execute.
            identifiers: The resource identifier(s) to pass to the action.

        Returns:
            List of results from the action execution.
        """
        try:
            logger.info(f"Running action {action.__class__.__name__} for {identifiers}")

            if isinstance(action, BatchAPIAction):
                return await action.execute_batch(identifiers)

            return await self._execute(action, identifiers)

        except Exception as e:
            logger.warning(f"Action {action.__class__.__name__} failed: {e}")
            return []

    async def _execute(
        self, action: Action, identifiers: List[str]
    ) -> List[Dict[str, Any]]:
        """Execute individual API calls concurrently with rate limiting."""
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def execute_single(identifier: str) -> Dict[str, Any]:
            async with semaphore:
                return await action.execute(identifier)

        tasks = [execute_single(identifier) for identifier in identifiers]
        return await asyncio.gather(*tasks)

    def _build_models(
        self, action_results: List[List[Dict[str, Any]]]
    ) -> List[ResourceModelT]:
        """
        Build resource models from action results.

        Args:
            action_results: List of result lists, one per action.

        Returns:
            List of built resource models.
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
        builder = ResourceBuilder(
            self.model_factory(), self.region or "", self.account_id or ""
        )

        builder.with_properties(identifier_results)

        return builder.build()
