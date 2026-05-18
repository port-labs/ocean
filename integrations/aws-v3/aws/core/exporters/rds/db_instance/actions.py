from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DescribeDBInstancesAction(Action):
    """Describe DB instances as a pass-through function."""

    async def _execute(
        self, db_instances: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return DB instances as is"""
        return db_instances


class ListTagsForResourceAction(Action):
    """Fetches tags for RDS DB instances."""

    async def _execute(
        self, db_instances: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch detailed tag information for the RDS DB instances."""

        tag_results = await asyncio.gather(
            *(self._fetch_tags(instance) for instance in db_instances),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        success_count = 0
        for idx, tag_result in enumerate(tag_results):
            if isinstance(tag_result, Exception):
                instance_id = db_instances[idx].get("DBInstanceIdentifier", "unknown")
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for DB instance '{instance_id}' : {tag_result}"
                    )
                    results.append({})
                    continue
                else:
                    logger.error(
                        f"Error fetching tags for DB instance '{instance_id}': {tag_result}"
                    )
                    raise tag_result
            results.extend(cast(list[dict[str, Any]], tag_result))
            success_count += 1
        logger.info(f"Successfully fetched tags for {success_count} DB instances")
        return results

    async def _fetch_tags(self, db_instance: dict[str, Any]) -> list[dict[str, Any]]:
        response = await self.client.list_tags_for_resource(
            ResourceName=db_instance["DBInstanceArn"]
        )
        return [{"Tags": response["TagList"]}]


class RdsDbInstanceActionsMap(ActionMap):
    defaults: list[Type[Action]] = [
        DescribeDBInstancesAction,
    ]
    options: list[Type[Action]] = [
        ListTagsForResourceAction,
    ]
