from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.action_execution.actions import (
    CodePipelineActionExecutionActionsMap,
    CodePipelineActionExecutionInput,
)
from aws.core.exporters.codepipeline.action_execution.models import (
    CodePipelineActionExecution,
    SingleCodePipelineActionExecutionRequest,
    PaginatedCodePipelineActionExecutionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodePipelineActionExecutionExporter(
    IResourceExporter[CodePipelineActionExecutionInput]
):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[CodePipelineActionExecution] = CodePipelineActionExecution
    _actions_map: Type[CodePipelineActionExecutionActionsMap] = (
        CodePipelineActionExecutionActionsMap
    )

    async def get_resource(
        self, options: SingleCodePipelineActionExecutionRequest
    ) -> dict[str, Any]:
        """Fetch a single CodePipeline action execution by ID."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await inspector.inspect(
                CodePipelineActionExecutionInput(
                    items=[{"name": options.pipeline_name}],
                    region=options.region,
                    account_id=options.account_id,
                ),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )

            if response:
                for execution in response:
                    if (
                        execution.get("actionExecutionId")
                        == options.action_execution_id
                    ):
                        return execution

            return {}

    async def get_paginated_resources(
        self, options: PaginatedCodePipelineActionExecutionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodePipeline action executions in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            paginator = proxy.get_paginator("list_pipelines", "pipelines")

            async for pipelines in paginator.paginate():
                if pipelines:
                    action_result = await inspector.inspect(
                        CodePipelineActionExecutionInput(
                            items=pipelines,
                            region=options.region,
                            account_id=options.account_id,
                        ),
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
