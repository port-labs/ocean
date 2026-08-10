from typing import List, Dict, Any, Callable
from loguru import logger
import asyncio
from aws.core.interfaces.action import Action, ActionMap, ActionInputType
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ResourceModel
from collections import defaultdict


class ResourceInspector[
    ResourceModelT: ResourceModel[Any], ActionInput: ActionInputType
]:
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
        actions_map: ActionMap[ActionInput],
        model_factory: Callable[[], ResourceModelT],
        action_id_key: str | None = None,
    ) -> None:
        """
        Initialize the ResourceInspector.

        Args:
            client: The AWS client instance to be used by actions.
            actions_map: The map of available actions for the resource.
            model_factory: A callable that returns a new instance of the resource model.
        """
        self.client = client
        self.actions_map = actions_map
        self.model_factory = model_factory
        self.action_id_key = action_id_key

    async def inspect(
        self,
        identifiers: ActionInput,
        include: List[str],
        extra_context: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute the specified actions for the given resource identifiers and
        aggregate their results into a resource model.

        Args:
            identifiers: A single resource identifier or a list of identifiers (e.g., ARNs, names).
            include: A list of action names to include in the inspection.

        Returns:
            List[Dict[str, Any]]: List of constructed resource models with aggregated data.
        """
        action_classes = self.actions_map.merge(include)
        actions = [cls(self.client) for cls in action_classes]
        template = self.model_factory()
        model_cls = type(template)
        resource_type = template.Type
        action_results = await asyncio.gather(
            *(self._run_action(action, identifiers) for action in actions),
        )

        if not action_results or not any(action_results):
            return []

        resource_data: dict[int | str, dict[str, Any]] = defaultdict(dict)
        if self.action_id_key:
            for result_group in action_results:
                for result in result_group:
                    if self.action_id_key in result:
                        resource_data[result[self.action_id_key]] |= result
                    else:
                        logger.warning(
                            f"Missing key '{self.action_id_key}' in result: {result}, skipping ..."
                        )
        else:
            for action_result in action_results:
                for idx, item in enumerate(action_result):
                    if item:
                        resource_data[idx] |= item

        resources = []
        for resource_props in resource_data.values():
            builder = ResourceBuilder[ResourceModelT](model_cls)
            builder.with_properties(resource_props)
            if extra_context:
                builder.with_extra_context(extra_context)
            builder.with_type(resource_type)
            resources.append(builder.build())

        logger.info(
            f"Built {len(resources)} resources from {len(action_results)} actions for {resource_type}"
        )
        return resources

    async def _run_action(
        self, action: Action[ActionInput], identifiers: ActionInput
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
