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

            paginator = proxy.get_paginator("list_pipelines", "pipelines")
            async for pipelines in paginator.paginate():
                if pipelines:
                    action_result = await inspector.inspect(
                        pipelines,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
