from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.dynamodb.table.actions import (
    DynamoDBTableActionsMap,
    DynamoDBTableActionInput,
    TableIdentifier,
)
from aws.core.exporters.dynamodb.table.models import (
    Table,
    SingleTableRequest,
    PaginatedTableRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from aws.utils import RegionHelper


class DynamoDBTableExporter(IResourceExporter[DynamoDBTableActionInput]):
    _service_name: SupportedServices = "dynamodb"
    _model_cls: Type[Table] = Table
    _actions_map: Type[DynamoDBTableActionsMap] = DynamoDBTableActionsMap

    async def get_resource(self, options: SingleTableRequest) -> dict[str, Any]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single-table fetch only has a table name from CloudTrail.
            # The inspector would still build a stub resource from ListTablesAction
            # even if the table is gone. Confirm it exists so a missing table raises
            # and the live-event handler can treat the update as a delete instead.
            await proxy.client.describe_table(  # type: ignore[attr-defined]
                TableName=options.table_name
            )

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            partition = RegionHelper.get_partition()
            result = await inspector.inspect(
                DynamoDBTableActionInput(
                    items=[
                        TableIdentifier(
                            table_name=options.table_name,
                            table_arn=f"arn:{partition}:dynamodb:{options.region}:{options.account_id}:table/{options.table_name}",
                        )
                    ],
                    region=options.region,
                    account_id=options.account_id,
                ),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedTableRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_tables", "TableNames")
            partition = RegionHelper.get_partition()

            async for table_names in paginator.paginate():
                table_items = [
                    TableIdentifier(
                        table_name=table_name,
                        table_arn=f"arn:{partition}:dynamodb:{options.region}:{options.account_id}:table/{table_name}",
                    )
                    for table_name in table_names
                ]
                result = await inspector.inspect(
                    DynamoDBTableActionInput(
                        items=table_items,
                        region=options.region,
                        account_id=options.account_id,
                    ),
                    options.include,
                    extra_context={
                        "AccountId": options.account_id,
                        "Region": options.region,
                    },
                )
                yield result
