from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.dynamodb.table.actions import DynamoDBTableActionsMap
from aws.core.exporters.dynamodb.table.models import DynamoDBTable
from aws.core.exporters.dynamodb.table.models import (
    SingleDynamoDBTableRequest,
    PaginatedDynamoDBTableRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class DynamoDBTableExporter(IResourceExporter[list[str]]):
    _service_name: SupportedServices = "dynamodb"
    _model_cls: Type[DynamoDBTable] = DynamoDBTable
    _actions_map: Type[DynamoDBTableActionsMap] = DynamoDBTableActionsMap

    async def get_resource(
        self, options: SingleDynamoDBTableRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single DynamoDB table."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [options.table_name],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedDynamoDBTableRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all DynamoDB tables in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            paginator = proxy.get_paginator("list_tables", "TableNames")

            async for table_names in paginator.paginate():
                if table_names:
                    action_result = await inspector.inspect(
                        table_names,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
