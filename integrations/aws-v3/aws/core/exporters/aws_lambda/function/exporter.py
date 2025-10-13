from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.aws_lambda.function.actions import LambdaFunctionActionsMap
from aws.core.exporters.aws_lambda.function.models import LambdaFunction
from aws.core.exporters.aws_lambda.function.models import (
    SingleLambdaFunctionRequest,
    PaginatedLambdaFunctionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class LambdaFunctionExporter(IResourceExporter):
    _service_name: SupportedServices = "lambda"
    _model_cls: Type[LambdaFunction] = LambdaFunction
    _actions_map: Type[LambdaFunctionActionsMap] = LambdaFunctionActionsMap

    async def get_resource(
        self, options: SingleLambdaFunctionRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single Lambda function."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await proxy.client.get_function(  # type: ignore[attr-defined]
                FunctionName=options.function_name
            )

            function = response["Configuration"]
            action_result = await inspector.inspect(
                [function],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedLambdaFunctionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all Lambda functions in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_functions", "Functions")

            async for functions in paginator.paginate():
                if functions:
                    action_result = await inspector.inspect(
                        functions,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
