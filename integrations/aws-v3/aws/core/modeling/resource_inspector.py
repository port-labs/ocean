from typing import List, Dict, Any, Callable, Union
from loguru import logger
import asyncio
from aws.core.interfaces.action import Action, ActionMap
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ResourceModel

TIdentifier = Union[str, int, Dict[str, Any] | List[Dict[str, Any]]]


class ResourceInspector[ResourceModelT: ResourceModel[Any]]:
    """
    Inspects AWS resources by executing a set of actions and aggregating their results
    into a strongly-typed resource model.

    This class orchestrates the execution of multiple `IAction` implementations (as defined
    in the provided `IActionMap`) for a given resource identifier or list of identifiers.
    The results of these actions are merged into a resource model using a builder pattern.

    Type Parameters:
        ResourceModelT: A subclass of `BaseResponseModel` representing the resource type.

    Args:
        client: The AWS client instance used by actions to interact with AWS services.
        actions_map: An `IActionMap` that provides the set of actions to execute.
        model_factory: A callable that returns a new instance of the resource model.

    Example:
        inspector = ResourceInspector(client, actions_map, MyResourceModel)
        resource = await inspector.inspect("resource-arn", include=["Describe", "Tags"])
    """

    def __init__(
        self,
        client: Any,
        actions_map: ActionMap,
        model_factory: Callable[[], ResourceModelT],
    ) -> None:
        """
        Initialize the ResourceInspector.

        Args:
            client: The AWS client instance to be used by actions.
            actions_map: The map of available actions for the resource.
            model_factory: A callable that returns a new instance of the resource model.
        """
        self.client = client
        self.builder_cls: ResourceBuilder[ResourceModelT, Any] = ResourceBuilder(
            model_factory()
        )
        self.actions_map = actions_map
        self.model_factory = model_factory

    async def inspect(
        self, identifiers: Any, include: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Execute the specified actions for the given resource identifiers and
        aggregate their results into a resource model.

        Args:
            identifiers: A single resource identifier or a list of identifiers (e.g., ARNs, names).
            include: A list of action names to include in the inspection.

        Returns:
            ResourceModelT: The constructed resource model with aggregated data.
        """
        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]

        action_results = await asyncio.gather(
            *(self._run_action(action, identifiers) for action in actions)
        )

        resources: List[Dict[str, Any]] = []
        for action_result in action_results:
            # Clone the builder before applying building
            builder = type(self.builder_cls)(self.model_factory())
            for action_result_item in action_result:
                if not action_result_item:
                    continue
                builder.with_properties(action_result_item)
            built_resource = builder.build()
            resources.append(built_resource)
        return resources

    async def _run_action(
        self, action: "Action", identifiers: Any
    ) -> List[Dict[str, Any]]:
        """
        Execute a single action for the given identifiers, handling exceptions gracefully.

        Args:
            action: The action instance to execute.
            identifiers: The resource identifier(s) to pass to the action.

        Returns:
            Dict[str, Any]: The result of the action, or an empty dict if the action fails.
        """
        try:
            return await action.execute(identifiers)
        except Exception as e:
            logger.warning(f"{action.__class__.__name__} failed: {e}, skipping ...")
            return []
