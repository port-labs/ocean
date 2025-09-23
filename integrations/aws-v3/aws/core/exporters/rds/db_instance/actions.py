from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class DescribeDBInstancesAction(Action):
    """Describe DB instances as a pass-through function."""

    async def _execute(
        self, db_instances: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return DB instances as is"""
        return db_instances


class ListTagsForResourceAction(Action):
    """Fetches tags for RDS DB instances."""

    async def _execute(
        self, db_instances: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fetch detailed tag information for the RDS DB instances."""

        tag_results = await asyncio.gather(
            *(self._fetch_tags(instance) for instance in db_instances),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tag_results):
            if isinstance(tag_result, Exception):
                instance_id = db_instances[idx].get("DBInstanceIdentifier", "unknown")
                logger.error(
                    f"Error fetching tags for DB instance '{instance_id}': {tag_result}"
                )
                continue
            results.extend(cast(List[Dict[str, Any]], tag_result))
        logger.info(f"Successfully fetched tags for {len(db_instances)} DB instances")
        return results

    async def _fetch_tags(self, db_instance: Dict[str, Any]) -> List[Dict[str, Any]]:
        response = await self.client.list_tags_for_resource(
            ResourceName=db_instance["DBInstanceArn"]
        )
        return [{"Tags": response["TagList"]}]


class RdsDbInstanceActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        DescribeDBInstancesAction,
    ]
    options: List[Type[Action]] = [
        ListTagsForResourceAction,
    ]
