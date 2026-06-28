from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ec2.volume_attachment.actions import EC2VolumeAttachmentActionsMap
from aws.core.exporters.ec2.volume_attachment.models import (
    EC2VolumeAttachment,
    SingleEC2VolumeAttachmentRequest,
    PaginatedEC2VolumeAttachmentRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EC2VolumeAttachmentExporter(IResourceExporter[list[dict[str, Any]]]):
    """Exports AWS EC2 VolumeAttachments using the ec2:DescribeVolumes API."""

    _service_name: SupportedServices = "ec2"
    _model_cls: Type[EC2VolumeAttachment] = EC2VolumeAttachment
    _actions_map: Type[EC2VolumeAttachmentActionsMap] = EC2VolumeAttachmentActionsMap

    async def get_resource(
        self, options: SingleEC2VolumeAttachmentRequest
    ) -> dict[str, Any]:
        """Fetch attachment details for a single EBS volume."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            result = await inspector.inspect(
                [{"VolumeId": options.volume_id}],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedEC2VolumeAttachmentRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all EC2 VolumeAttachments in a region by iterating over volumes."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("describe_volumes", "Volumes")

            async for volumes in paginator.paginate():
                # Only process volumes that have attachments
                attached_volumes = [
                    v for v in volumes if v.get("Attachments")
                ]
                if attached_volumes:
                    action_result = await inspector.inspect(
                        attached_volumes,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
