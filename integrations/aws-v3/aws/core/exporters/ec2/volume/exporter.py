from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ec2.volume.actions import EbsVolumeActionsMap
from aws.core.exporters.ec2.volume.models import (
    EbsVolume,
    SingleEbsVolumeRequest,
    PaginatedEbsVolumeRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EbsVolumeExporter(IResourceExporter):
    """Exports AWS EBS volumes using the ec2:DescribeVolumes API."""

    _service_name: SupportedServices = "ec2"
    _model_cls: Type[EbsVolume] = EbsVolume
    _actions_map: Type[EbsVolumeActionsMap] = EbsVolumeActionsMap

    async def get_resource(self, options: SingleEbsVolumeRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single EBS volume."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await proxy.client.describe_volumes(  # type: ignore[attr-defined]
                VolumeIds=[options.volume_id]
            )
            volumes = response.get("Volumes", [])
            if not volumes:
                return {}
            result = await inspector.inspect(
                volumes,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedEbsVolumeRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all EBS volumes in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("describe_volumes", "Volumes")

            async for volumes in paginator.paginate():
                if volumes:
                    action_result = await inspector.inspect(
                        volumes,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
