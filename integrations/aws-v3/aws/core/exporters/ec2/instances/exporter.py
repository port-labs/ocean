import asyncio
import json
from typing import Any, AsyncGenerator, Type

from loguru import logger

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ec2.instances.actions import EC2InstanceActionsMap
from aws.core.exporters.ec2.instances.models import EC2Instance
from aws.core.exporters.ec2.instances.models import (
    SingleEC2InstanceRequest,
    PaginatedEC2InstanceRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


def serialize_datetime_objects(data: Any) -> Any:
    """Convert datetime objects to ISO strings for JSON serialization."""
    return json.loads(json.dumps(data, default=str))


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
                self.account_id,
                options.region,
            )
            response = await inspector.inspect(options.instance_id, options.include)

            return serialize_datetime_objects(response.dict(exclude_none=True))

    async def _process_instance(
        self,
        instance: dict[str, Any],
        inspector: ResourceInspector[EC2Instance],
        include: list[str],
    ) -> dict[str, Any]:
        """Process a single instance with its describe_instances data and actions."""

        # Follow ECS pattern: use ResourceBuilder to combine initial data with action data
        from aws.core.modeling.resource_builder import ResourceBuilder

        # Create builder with proper account ID
        builder: Any = ResourceBuilder(
            self._model_cls(), account_id=self.account_id, region=inspector.region
        )

        # Add the initial describe_instances data as the first property
        properties_data: list[Any] = [instance]

        # Add action data if any actions are included
        if include:
            action_result = await inspector.inspect(instance["InstanceId"], include)
            if action_result.Properties:
                action_properties = action_result.Properties.dict(exclude_none=True)
                if action_properties:
                    properties_data.append(action_properties)

        builder.with_properties(properties_data)

        # Build the model with all data properly combined
        model = builder.build()

        return serialize_datetime_objects(model.dict(exclude_none=True))

    async def get_paginated_resources(
        self, options: PaginatedEC2InstanceRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of EC2 instance information, fetched using pagination."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
                self.account_id,
                options.region,
            )
            paginator = proxy.get_paginator("describe_instances", "Reservations")

            async for reservations in paginator.paginate():
                logger.info(
                    f"EC2 describe_instances returned {len(reservations)} reservations"
                )

                # Extract all instances from all reservations
                instances = []
                for reservation in reservations:
                    instances.extend(reservation.get("Instances", []))

                if not instances:
                    continue

                logger.info(f"Found {len(instances)} instances in reservations")

                # Process instances concurrently using Regional Individual pattern
                tasks = [
                    self._process_instance(instance, inspector, options.include)
                    for instance in instances
                ]
                instance_results = await asyncio.gather(*tasks)

                logger.info(instance_results)

                yield instance_results
