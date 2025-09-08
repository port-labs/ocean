from typing import Dict, Any, List, Type
from aws.core.interfaces.action import (
    Action,
    ActionMap,
)
from loguru import logger


class GetInstanceStatusAction(Action):
    async def _execute(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch detailed status information for the EC2 instance."""

        response = await self.client.describe_instance_status(
            InstanceIds=[instance["InstanceId"] for instance in instances],
            IncludeAllInstances=True,
        )
        logger.info(
            f"Successfully fetched instance status for {len(instances)} instances"
        )
        return response["InstanceStatuses"]


class DescribeInstancesAction(Action):
    async def _execute(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return instances as is"""
        return instances


class EC2InstanceActionsMap(ActionMap):
    defaults: List[Type[Action]] = [DescribeInstancesAction, GetInstanceStatusAction]
    options: List[Type[Action]] = []

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        logger.info(
            f"Merging actions. Defaults: {[action.__name__ for action in self.defaults]}, Options: {[action.__name__ for action in self.options]}, Include: {include}"
        )
        merged = self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
        logger.debug(f"Merged actions: {[action.__name__ for action in merged]}")
        return merged
