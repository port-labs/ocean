from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.rds.db_instance.actions import RdsDbInstanceActionsMap
from aws.core.exporters.rds.db_instance.models import DbInstance
from aws.core.exporters.rds.db_instance.models import (
    SingleDbInstanceRequest,
    PaginatedDbInstanceRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class RdsDbInstanceExporter(IResourceExporter):
    _service_name: SupportedServices = "rds"
    _model_cls: Type[DbInstance] = DbInstance
    _actions_map: Type[RdsDbInstanceActionsMap] = RdsDbInstanceActionsMap

    async def get_resource(self, options: SingleDbInstanceRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single RDS DB instance."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await proxy.client.describe_db_instances(  # type: ignore[attr-defined]
                DBInstanceIdentifier=options.db_instance_identifier
            )

            db_instance = response["DBInstances"]
            action_result = await inspector.inspect(
                db_instance,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedDbInstanceRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all RDS DB instances in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("describe_db_instances", "DBInstances")

            async for db_instances in paginator.paginate():
                if db_instances:
                    action_result = await inspector.inspect(
                        db_instances,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
