from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.apigateway.rest_api.actions import RestApiActionsMap
from aws.core.exporters.apigateway.rest_api.models import RestApi
from aws.core.exporters.apigateway.rest_api.models import (
    SingleRestApiRequest,
    PaginatedRestApiRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class RestApiExporter(IResourceExporter):
    _service_name: SupportedServices = "apigateway"
    _model_cls: Type[RestApi] = RestApi
    _actions_map: Type[RestApiActionsMap] = RestApiActionsMap

    async def get_resource(self, options: SingleRestApiRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single REST API."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"Id": options.rest_api_id, "id": options.rest_api_id}], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedRestApiRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all REST APIs in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Use the appropriate paginator for API Gateway service
            paginator = proxy.get_paginator("get_rest_apis", "items")

            async for resources in paginator.paginate():
                if resources:
                    # Transform resources to match expected format
                    formatted_resources = []
                    for resource in resources:
                        formatted_resources.append({
                            "id": resource["id"],
                            "name": resource.get("name", ""),
                            "description": resource.get("description"),
                            "createdDate": resource.get("createdDate"),
                            "version": resource.get("version"),
                            "binaryMediaTypes": resource.get("binaryMediaTypes", []),
                            "minimumCompressionSize": resource.get("minimumCompressionSize"),
                            "apiKeySource": resource.get("apiKeySource"),
                            "endpointConfiguration": resource.get("endpointConfiguration"),
                            "policy": resource.get("policy"),
                            "disableExecuteApiEndpoint": resource.get("disableExecuteApiEndpoint"),
                        })
                    
                    action_result = await inspector.inspect(
                        formatted_resources,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []