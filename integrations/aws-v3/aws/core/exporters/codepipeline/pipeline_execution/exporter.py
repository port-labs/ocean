from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.pipeline_execution.actions import CodePipelinePipelineExecutionActionsMap
from aws.core.exporters.codepipeline.pipeline_execution.models import PipelineExecution
from aws.core.exporters.codepipeline.pipeline_execution.models import (
    SinglePipelineExecutionRequest,
    PaginatedPipelineExecutionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodePipelinePipelineExecutionExporter(IResourceExporter):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[PipelineExecution] = PipelineExecution
    _actions_map: Type[CodePipelinePipelineExecutionActionsMap] = CodePipelinePipelineExecutionActionsMap

    async def get_resource(self, options: SinglePipelineExecutionRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single pipeline execution."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            # Create a mock execution object for the inspector
            mock_execution = {
                "pipelineName": options.pipeline_name,
                "pipelineExecutionId": options.pipeline_execution_id
            }

            response = await inspector.inspect(
                [mock_execution],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedPipelineExecutionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all pipeline executions in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            pipeline_paginator = proxy.get_paginator("list_pipelines", "pipelines")
            execution_paginator = proxy.get_paginator("list_pipeline_executions", "pipelineExecutionSummaries")

            async for pipelines in pipeline_paginator.paginate():
                for pipeline in pipelines:
                    async for executions in execution_paginator.paginate(pipelineName=pipeline["name"]):
                        yield await inspector.inspect(
                            executions,
                            options.include,
                            extra_context={
                                "AccountId": options.account_id,
                                "Region": options.region,
                            },
                        )
