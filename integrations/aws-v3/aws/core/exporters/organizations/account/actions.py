from typing import Any, List, Type, Union

from loguru import logger

from aws.core.interfaces.action import Action, ActionMap, BatchAction


class ListTagsAction(Action):
    """List tags for an AWS Organizations account."""

    async def _execute(self, identifier: str) -> dict[str, Any]:
        """List tags for the specified account."""
        response = await self.client.list_tags_for_resource(ResourceId=identifier)  # type: ignore

        logger.info(f"Found {len(response['Tags'])} tags for account {identifier}")
        return {"Tags": response["Tags"]}


class OrganizationsAccountActionsMap(ActionMap):
    defaults: List[Type[Union[Action, BatchAction]]] = []  # No default actions needed
    options: List[Type[Union[Action, BatchAction]]] = [ListTagsAction]

    def merge(self, include: List[str]) -> List[Type[Union[Action, BatchAction]]]:
        """Merge default actions with requested optional actions."""
        if not include:
            return self.defaults

        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
