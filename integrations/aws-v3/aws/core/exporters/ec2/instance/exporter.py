from typing import Any, AsyncGenerator, Type, List, Dict

from loguru import logger

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ec2.instance.actions import EC2InstanceActionsMap
from aws.core.exporters.ec2.instance.models import EC2Instance
from aws.core.exporters.ec2.instance.models import (
    SingleEC2InstanceRequest,
    PaginatedEC2InstanceRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class EC2InstanceExporter(IResourceExporter):
    _service_name: SupportedServices = "ec2"
    _model_cls: Type[EC2Instance] = EC2Instance
    _actions_map: Type[EC2InstanceActionsMap] = EC2InstanceActionsMap

    async def get_resource(self, options: SingleEC2InstanceRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single EC2 instance."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:

            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
            )
            response = await inspector.inspect([options.instance_id], options.include)

            return response[0]

    async def get_paginated_resources(
        self, options: PaginatedEC2InstanceRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of EC2 instance information, fetched using pagination."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("describe_instances", "Reservations")

            async for reservations in paginator.paginate():
                logger.info(
                    f"EC2 describe_instances returned {len(reservations)} reservations"
                )
                for reservation in reservations:
                    instances: List[Dict[str, Any]] = reservation.pop("Instances")
                    action_result = await inspector.inspect(
                        instances,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                            **reservation,
                        },
                    )
                    yield action_result
