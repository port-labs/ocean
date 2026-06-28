from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class DescribeVolumeAttachmentsAction(Action[list[dict[str, Any]]]):
    """Fetches volume attachments by describing volumes and extracting attachment info."""

    async def _execute(self, volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=volumes,
            operation_func=self._fetch_volume_attachments,
            get_resource_identifier=lambda v: v.get("VolumeId", "unknown"),
            operation_name="volume attachment",
        )

    async def _fetch_volume_attachments(self, volume: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.describe_volumes(
            VolumeIds=[volume["VolumeId"]]
        )
        volumes = response.get("Volumes", [])
        if not volumes:
            return {}
        attachments = volumes[0].get("Attachments", [])
        if not attachments:
            return {}
        # Return the first attachment merged with volume context
        attachment = attachments[0]
        return {
            "VolumeId": volume["VolumeId"],
            "InstanceId": attachment.get("InstanceId", ""),
            "Device": attachment.get("Device"),
            "State": attachment.get("State"),
            "AttachTime": str(attachment["AttachTime"]) if attachment.get("AttachTime") else None,
            "DeleteOnTermination": attachment.get("DeleteOnTermination"),
        }


class EC2VolumeAttachmentActionsMap(ActionMap[list[dict[str, Any]]]):
    """Groups all actions for EC2 VolumeAttachment resources."""

    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        DescribeVolumeAttachmentsAction
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = []
