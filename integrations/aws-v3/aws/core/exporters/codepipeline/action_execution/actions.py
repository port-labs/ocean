from typing import Any, List, Type

from aws.core.interfaces.action import Action, ActionMap


class ListActionExecutionsAction(Action[list[dict[str, Any]]]):
    """Fetches action executions for all pipelines in the region."""

    async def _execute(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return resources


class CodePipelineActionExecutionActionsMap(ActionMap[list[dict[str, Any]]]):
    """Groups all actions for CodePipeline action executions."""

    defaults: List[Type[Action[list[dict[str, Any]]]]] = [
        ListActionExecutionsAction,
    ]
    options: List[Type[Action[list[dict[str, Any]]]]] = []
