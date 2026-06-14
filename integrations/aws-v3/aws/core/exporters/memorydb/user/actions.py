from typing import Any, Type

from aws.core.helpers.utils import execute_concurrent_aws_operations
from aws.core.interfaces.action import Action, ActionMap


class DescribeMemoryDbUsersAction(Action[list[dict[str, Any]]]):
    """Pass-through of user dicts returned from the describe_users paginator."""

    async def _execute(self, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return users


class ListTagsForMemoryDbUserAction(Action[list[dict[str, Any]]]):
    """Fetches tags for MemoryDB users via a separate list_tags call."""

    async def _execute(self, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=users,
            operation_func=self._fetch_tags,
            get_resource_identifier=lambda user: user["Name"],
            operation_name="tags for MemoryDB user",
        )

    async def _fetch_tags(self, user: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.list_tags(ResourceArn=user["ARN"])
        return {"TagList": response["TagList"]}


class MemoryDbUserActionsMap(ActionMap):
    defaults: list[Type[Action]] = [DescribeMemoryDbUsersAction]
    options: list[Type[Action]] = [ListTagsForMemoryDbUserAction]
