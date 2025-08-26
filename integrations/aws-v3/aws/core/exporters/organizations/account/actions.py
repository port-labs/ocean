from typing import List, Type, Dict, Any
from loguru import logger
from aws.core.interfaces.action import Action, APIAction, ActionMap


class ListTagsAction(APIAction):
    """List tags for an AWS Organizations account."""

    async def _execute(self, identifier: str) -> Dict[str, Any]:
        """List tags for the specified account."""
        logger.info(f"Listing tags for account {identifier}")

        response = await self.client.list_tags_for_resource(ResourceId=identifier)  # type: ignore

        logger.info(f"Found {len(response['Tags'])} tags for account {identifier}")
        return {"Tags": response["Tags"]}


class OrganizationsAccountActionsMap(ActionMap):
    defaults: List[Type[Action]] = []
    options: List[Type[Action]] = [ListTagsAction]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        """Merge default actions with requested optional actions."""
        if not include:
            return self.defaults

        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
