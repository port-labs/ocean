from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.pipeline.actions import PipelineActionsMap
from aws.core.exporters.codepipeline.pipeline.models import Pipeline
from aws.core.exporters.codepipeline.pipeline.models import (
    SinglePipelineRequest,
    PaginatedPipelineRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class PipelineExporter(IResourceExporter):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[Pipeline] = Pipeline
    _actions_map: Type[PipelineActionsMap] = PipelineActionsMap

    async def get_resource(self, options: SinglePipelineRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodePipeline pipeline."""
        async with AioBaseClientProxy(self.session, options.region, self._service_name) as proxy:
            inspector = ResourceInspector(proxy.client, self._actions_map(), lambda: self._model_cls())
            response = await inspector.inspect([{"name": options.pipeline_name}], options.include)
            return response[0] if response else {}

    async def get_paginated_resources(self, options: PaginatedPipelineRequest) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodePipeline pipelines in a region."""
        async with AioBaseClientProxy(self.session, options.region, self._service_name) as proxy:
            inspector = ResourceInspector(proxy.client, self._actions_map(), lambda: self._model_cls())

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
