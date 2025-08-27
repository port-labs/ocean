from typing import Dict, Any, List, Type
from aws.core.interfaces.action import (
    Action,
    APIAction,
    ActionMap,
)
from loguru import logger


class GetInstanceStatusAction(APIAction):
    async def _execute(self, instance_id: str) -> Dict[str, Any]:
        """Fetch detailed status information for the EC2 instance."""
        response = await self.client.describe_instance_status(  # type: ignore
            InstanceIds=[instance_id], IncludeAllInstances=True
        )
        instance_statuses = response.get("InstanceStatuses", [])
        if instance_statuses:
            status_info = instance_statuses[0]
            return {
                "InstanceStatus": status_info.get("InstanceStatus"),
                "SystemStatus": status_info.get("SystemStatus"),
                "Events": status_info.get("Events", []),
            }
        logger.info(f"No status information found for instance {instance_id}")
        return {}


class EC2InstanceActionsMap(ActionMap):
    defaults: List[Type[Action]] = []
    options: List[Type[Action]] = [
        GetInstanceStatusAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
