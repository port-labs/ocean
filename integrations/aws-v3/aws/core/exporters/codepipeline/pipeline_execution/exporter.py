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

            # First, get all pipelines in the region
            pipelines_response = await proxy.client.list_pipelines()
            pipelines = pipelines_response.get("pipelines", [])
            
            # If a specific pipeline name is provided, filter to that pipeline
            if options.pipeline_name:
                pipelines = [p for p in pipelines if p["name"] == options.pipeline_name]

            # For each pipeline, get its executions
            for pipeline in pipelines:
                pipeline_name = pipeline["name"]
                
                # Use pagination for pipeline executions
                paginator_kwargs = {
                    "pipelineName": pipeline_name
                }
                if options.max_results:
                    paginator_kwargs["maxResults"] = options.max_results

                try:
                    paginator = proxy.client.get_paginator("list_pipeline_executions")
                    page_iterator = paginator.paginate(**paginator_kwargs)
                    
                    async for page in page_iterator:
                        executions = page.get("pipelineExecutionSummaries", [])
                        if executions:
                            # Add pipeline name to each execution for context
                            for execution in executions:
                                execution["pipelineName"] = pipeline_name
                            
                            action_result = await inspector.inspect(
                                executions,
                                options.include,
                                extra_context={
                                    "AccountId": options.account_id,
                                    "Region": options.region,
                                },
                            )
                            yield action_result
                        else:
                            yield []
                            
                except Exception as e:
                    # Log error and continue with next pipeline
                    from loguru import logger
                    logger.error(f"Error fetching executions for pipeline '{pipeline_name}': {e}")
                    yield []