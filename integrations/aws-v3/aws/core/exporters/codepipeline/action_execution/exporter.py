from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.action_execution.actions import ActionExecutionActionsMap
from aws.core.exporters.codepipeline.action_execution.models import ActionExecution
from aws.core.exporters.codepipeline.action_execution.models import (
    SingleActionExecutionRequest,
    PaginatedActionExecutionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class ActionExecutionExporter(IResourceExporter):
    """Exporter for AWS CodePipeline ActionExecution resources."""
    
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[ActionExecution] = ActionExecution
    _actions_map: Type[ActionExecutionActionsMap] = ActionExecutionActionsMap

    async def get_resource(self, options: SingleActionExecutionRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ActionExecution."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # For single action execution, we need to provide the pipeline context
            response = await inspector.inspect(
                [{
                    "pipeline_name": options.pipeline_name,
                    "action_execution_id": options.action_execution_id,
                }], 
                options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedActionExecutionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ActionExecution resources in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Start with empty initial data - the actions will populate the pipeline list
            initial_resources = [{}]
            
            action_result = await inspector.inspect(
                initial_resources,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                    "PipelineFilter": options.pipeline_name,  # Optional filter
                },
            )
            
            # Since CodePipeline action executions can be numerous, we yield them in batches
            batch_size = 50
            for i in range(0, len(action_result), batch_size):
                batch = action_result[i:i + batch_size]
                yield batch