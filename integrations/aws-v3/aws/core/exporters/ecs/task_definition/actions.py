from typing import Dict, Any, List, Type

from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class ListTaskDefinitionsAction(Action):
    async def _execute(self, task_definition_arns: List[str]) -> List[Dict[str, Any]]:
        return [{"TaskDefinitionArn": arn} for arn in task_definition_arns]


class DescribeTaskDefinitionsAction(Action):
    """Describes task definitions concurrently (API accepts one ARN per call)."""

    async def _execute(self, task_definition_arns: List[str]) -> List[Dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=task_definition_arns,
            operation_func=self._fetch_task_definition,
            get_resource_identifier=lambda arn: arn,
            operation_name="task definition",
        )

    async def _fetch_task_definition(self, arn: str) -> Dict[str, Any]:
        response = await self.client.describe_task_definition(
            taskDefinition=arn, include=["TAGS"]
        )
        task_definition = response["taskDefinition"]
        task_definition["Tags"] = response.get("tags", [])
        return task_definition


class EcsTaskDefinitionActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        ListTaskDefinitionsAction,
        DescribeTaskDefinitionsAction,
    ]
    options: List[Type[Action]] = []
