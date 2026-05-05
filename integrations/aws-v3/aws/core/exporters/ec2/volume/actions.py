from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class DescribeVolumesAction(Action):
    """Pass-through; describe_volumes returns all required fields including tags."""

    async def _execute(self, volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return volumes


class DescribeVolumeAttributeAction(Action):
    """Fetches AutoEnableIO attribute for each volume (requires ec2:DescribeVolumeAttribute)."""

    async def _execute(self, volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=volumes,
            operation_func=self._fetch_auto_enable_io,
            get_resource_identifier=lambda v: v["VolumeId"],
            operation_name="volume attribute",
        )

    async def _fetch_auto_enable_io(self, volume: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.describe_volume_attribute(
            VolumeId=volume["VolumeId"], Attribute="autoEnableIO"
        )
        return {"AutoEnableIO": response["AutoEnableIO"]["Value"]}


class EbsVolumeActionsMap(ActionMap):
    """Groups all actions for EBS volumes."""

    defaults: list[Type[Action]] = [DescribeVolumesAction]
    options: list[Type[Action]] = [DescribeVolumeAttributeAction]
