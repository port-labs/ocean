from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import (
    Action,
    ActionMap,
)
from loguru import logger
import asyncio


class DescribeInstanceStatusAction(Action):
    async def _execute(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch detailed status information for the EC2 instances."""

        status_results = await asyncio.gather(
            *(self._fetch_instance_status(instance) for instance in instances),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, status_result in enumerate(status_results):
            if isinstance(status_result, Exception):
                instance_id = instances[idx].get("InstanceId", "unknown")
                logger.error(
                    f"Error fetching instance status for instance '{instance_id}': {status_result}"
                )
                continue
            results.extend(cast(List[Dict[str, Any]], status_result))
        logger.info(
            f"Successfully fetched instance status for {len(instances)} instances"
        )
        return results

    async def _fetch_instance_status(
        self, instance: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        response = await self.client.describe_instance_status(
            InstanceIds=[instance["InstanceId"]],
            IncludeAllInstances=True,
        )
        return response["InstanceStatuses"]


class DescribeInstancesAction(Action):
    async def _execute(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return instances as is"""
        return instances


class EC2InstanceActionsMap(ActionMap):
    defaults: List[Type[Action]] = [DescribeInstancesAction]
    options: List[Type[Action]] = [DescribeInstanceStatusAction]
