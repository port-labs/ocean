from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.stage.actions import CodePipelineStageActionsMap
from aws.core.exporters.codepipeline.stage.models import CodePipelineStage
from aws.core.exporters.codepipeline.stage.models import (
    SingleCodePipelineStageRequest,
    PaginatedCodePipelineStageRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class CodePipelineStageExporter(IResourceExporter):
    """Exporter for CodePipeline stages."""
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[CodePipelineStage] = CodePipelineStage
    _actions_map: Type[CodePipelineStageActionsMap] = CodePipelineStageActionsMap

    async def get_resource(self, options: SingleCodePipelineStageRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodePipeline stage."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Create a resource identifier for the specific stage
            resource_id = {
                "PipelineName": options.pipeline_name,
                "Name": options.stage_name,
                "pipeline_name": options.pipeline_name,
                "stage_name": options.stage_name,
            }
            
            response = await inspector.inspect(
                [resource_id], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedCodePipelineStageRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodePipeline stages in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # CodePipeline doesn't have built-in pagination for stages since stages are part of pipelines
            # We need to list all pipelines first, then extract stages
            try:
                logger.info(f"Fetching CodePipeline stages from region {options.region}")
                
                # Pass an empty list to trigger the ListPipelinesAction
                # which will discover all pipelines and their stages
                action_result = await inspector.inspect(
                    [],  # Empty list triggers pipeline discovery
                    options.include,
                    extra_context={
                        "AccountId": options.account_id,
                        "Region": options.region,
                    },
                )
                
                if action_result:
                    logger.info(f"Found {len(action_result)} CodePipeline stages in region {options.region}")
                    yield action_result
                else:
                    logger.info(f"No CodePipeline stages found in region {options.region}")
                    yield []
                    
            except Exception as e:
                logger.error(f"Error fetching CodePipeline stages from region {options.region}: {e}")
                yield []