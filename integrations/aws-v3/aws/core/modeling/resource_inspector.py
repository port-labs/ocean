from typing import List, Dict, Any, Callable, Union
from loguru import logger
import asyncio
from aws.core.interfaces.action import Action, ActionMap, BatchAction
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
        account_id: str,
        region: str,
    ) -> None:
        """
        Initialize the ResourceInspector.

        Args:
            client: The AWS client instance to be used by actions.
            actions_map: The map of available actions for the resource.
            model_factory: A callable that returns a new instance of the resource model.
            account_id: The AWS account ID for this resource (required).
            region: The AWS region for this resource (required).
        """
        self.client = client
        self.actions_map = actions_map
        self.model_factory = model_factory
        self.region = region
        self.account_id = account_id

    async def inspect(self, identifier: str, include: List[str]) -> ResourceModelT:
        """Inspect a single resource using single actions only."""
        if not identifier:
            return self.model_factory()

        # Execute single actions directly for single resource
        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]

        # Only execute Action types (single resource operations)
        single_actions = [action for action in actions if isinstance(action, Action)]

        if not single_actions:
            # If no single actions, return empty model
            return self.model_factory()

        results = await asyncio.gather(
            *(action.execute(identifier) for action in single_actions)
        )

        return self._build_model(results)

    async def inspect_batch(
        self, identifiers: List[str], include: List[str]
    ) -> List[ResourceModelT]:
        """Inspect multiple resources using both Action and BatchAction types."""
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
        self, action: Union[Action, BatchAction], identifiers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Execute a single action for the given identifiers using pure polymorphism.

        Args:
            action: The action instance to execute (either Action or BatchAction).
            identifiers: The resource identifier(s) to pass to the action.

        Returns:
            List of results from the action execution.
        """
        try:
            logger.info(
                f"Running action {action.__class__.__name__} for {len(identifiers)} identifiers"
            )

            # Pure polymorphism - no type checking needed!
            return await action.execute_for_identifiers(identifiers)

        except Exception as e:
            logger.warning(f"Action {action.__class__.__name__} failed: {e}")
            return []

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
        builder: ResourceBuilder[ResourceModelT, Any] = ResourceBuilder(
            self.model_factory(), self.region, self.account_id
        )

        # Pass results directly to builder
        builder.with_properties(identifier_results)

        # Set metadata using the builder
        builder.with_metadata({"__AccountId": self.account_id, "__Region": self.region})

        # Build the model
        model = builder.build()

        return model
