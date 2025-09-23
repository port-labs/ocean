from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListTagsForResourceAction(Action):
    """Fetches tags for RDS DB instances."""

    async def _execute(self, db_instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not db_instances:
            return []

        # Get tags for each DB instance concurrently
        tag_results = await asyncio.gather(
            *(self._fetch_tags(instance) for instance in db_instances),
            return_exceptions=True
        )

        # Merge tags into the instances
        for idx, tag_result in enumerate(tag_results):
            if isinstance(tag_result, Exception):
                logger.warning(
                    f"Failed to fetch tags for DB instance {db_instances[idx].get('DBInstanceIdentifier', 'unknown')}: {tag_result}"
                )
                db_instances[idx]["Tags"] = []
            else:
                db_instances[idx]["Tags"] = tag_result.get("TagList", [])

        return db_instances

    async def _fetch_tags(self, db_instance: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_tags_for_resource(
                ResourceName=db_instance["DBInstanceArn"]
            )
            logger.debug(
                f"Successfully fetched tags for DB instance {db_instance.get('DBInstanceIdentifier', 'unknown')}"
            )
            return response
        except Exception as e:
            logger.error(
                f"Error fetching tags for DB instance {db_instance.get('DBInstanceIdentifier', 'unknown')}: {e}"
            )
            return {"TagList": []}


class RdsDbInstanceActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        # No default actions - paginator provides the data
    ]
    options: List[Type[Action]] = [
        ListTagsForResourceAction,
    ]
