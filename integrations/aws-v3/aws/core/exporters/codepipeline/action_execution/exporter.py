from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.action_execution.actions import (
    CodePipelineActionExecutionActionsMap,
)
from aws.core.exporters.codepipeline.action_execution.models import (
    CodePipelineActionExecution,
    SingleCodePipelineActionExecutionRequest,
    PaginatedCodePipelineActionExecutionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodePipelineActionExecutionExporter(IResourceExporter[list[dict[str, Any]]]):
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

            paginator = proxy.get_paginator(
                "list_action_executions", "actionExecutionDetails"
            )
            response_actions = []
            async for action_executions in paginator.paginate(
                pipelineName=options.pipeline_name
            ):
                response_actions.extend(
                    await inspector.inspect(
                        action_executions,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                )

            for execution in response_actions:
                if execution.get("actionExecutionId") == options.action_execution_id:
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

            pipeline_paginator = proxy.get_paginator("list_pipelines", "pipelines")
            action_paginator = proxy.get_paginator(
                "list_action_executions", "actionExecutionDetails"
            )

            async for pipelines in pipeline_paginator.paginate():
                for pipeline in pipelines:
                    async for action_executions in action_paginator.paginate(
                        pipelineName=pipeline["name"]
                    ):
                        yield await inspector.inspect(
                            action_executions,
                            options.include,
                            extra_context={
                                "AccountId": options.account_id,
                                "Region": options.region,
                            },
                        )
