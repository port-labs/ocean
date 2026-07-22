from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.dynamodb.table.actions import DynamoDBTableActionsMap
from aws.core.exporters.dynamodb.table.models import (
    Table,
    SingleTableRequest,
    PaginatedTableRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class DynamoDBTableExporter(IResourceExporter[list[dict[str, Any]]]):
    _service_name: SupportedServices = "dynamodb"
    _model_cls: Type[Table] = Table
    _actions_map: Type[DynamoDBTableActionsMap] = DynamoDBTableActionsMap

    async def get_resource(self, options: SingleTableRequest) -> dict[str, Any]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            table_dict = {
                "TableName": options.table_name,
                "TableArn": f"arn:aws:dynamodb:{options.region}:{options.account_id}:table/{options.table_name}",
            }
            result = await inspector.inspect(
                [table_dict],
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

            async for table_names in paginator.paginate():
                if table_names:
                    table_dicts = [
                        {
                            "TableName": table_name,
                            "TableArn": f"arn:aws:dynamodb:{options.region}:{options.account_id}:table/{table_name}",
                        }
                        for table_name in table_names
                    ]
                    result = await inspector.inspect(
                        table_dicts,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield result
                else:
                    yield []
