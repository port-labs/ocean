from typing import Any, AsyncGenerator, Type, List, Dict

from aws.core.helpers.utils import extract_ec2_instances, require_aws_resource
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


class EC2InstanceExporter(IResourceExporter[list[dict[str, Any]]]):
    _service_name: SupportedServices = "ec2"
    _model_cls: Type[EC2Instance] = EC2Instance
    _actions_map: Type[EC2InstanceActionsMap] = EC2InstanceActionsMap

    async def get_resource(self, options: SingleEC2InstanceRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single EC2 instance."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single-instance fetch only has an instance ID from CloudTrail.
            # Confirm it exists so a missing instance raises and the live-event
            # handler can treat the update as a delete instead.
            response = await proxy.client.describe_instances(  # type: ignore[attr-defined]
                InstanceIds=[options.instance_id]
            )
            instances = require_aws_resource(
                extract_ec2_instances(response),
                error_code="InvalidInstanceID.NotFound",
                message=f"Instance not found: {options.instance_id}",
                operation_name="DescribeInstances",
            )

            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
            )
            result = await inspector.inspect(
                instances,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )

            return result[0] if result else {}

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
