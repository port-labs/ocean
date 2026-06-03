from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.stage_execution.actions import CodePipelineStageExecutionActionsMap
from aws.core.exporters.codepipeline.stage_execution.models import CodePipelineStageExecution
from aws.core.exporters.codepipeline.stage_execution.models import (
    SingleStageExecutionRequest,
    PaginatedStageExecutionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodePipelineStageExecutionExporter(IResourceExporter):
    """Exporter for AWS CodePipeline stage executions."""
    
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[CodePipelineStageExecution] = CodePipelineStageExecution
    _actions_map: Type[CodePipelineStageExecutionActionsMap] = CodePipelineStageExecutionActionsMap

    async def get_resource(self, options: SingleStageExecutionRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single stage execution."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Create a mock resource to fetch this specific stage execution
            mock_resource = {
                "pipelineName": options.pipeline_name,
                "pipelineExecutionId": options.pipeline_execution_id,
            }
            
            response = await inspector.inspect(
                [mock_resource], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedStageExecutionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all stage executions in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Start with an empty list to trigger the pipeline discovery
            # The actions will handle fetching pipelines -> executions -> stage executions
            action_result = await inspector.inspect(
                [],  # Empty list triggers pipeline discovery
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            
            if action_result:
                yield action_result
            else:
                yield []