from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.stage.actions import (
    CodePipelineStageActionsMap,
    GetPipelineStagesInput,
)
from aws.core.exporters.codepipeline.stage.models import CodePipelineStage
from aws.core.exporters.codepipeline.stage.models import (
    SingleCodePipelineStageRequest,
    PaginatedCodePipelineStageRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodePipelineStageExporter(IResourceExporter[GetPipelineStagesInput]):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[CodePipelineStage] = CodePipelineStage
    _actions_map: Type[CodePipelineStageActionsMap] = CodePipelineStageActionsMap

    async def get_resource(
        self, options: SingleCodePipelineStageRequest
    ) -> dict[str, Any]:
        """Fetch a single CodePipeline stage by pipeline name and stage name."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            results = await inspector.inspect(
                GetPipelineStagesInput(
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
            # Filter to the specific stage requested
            for result in results:
                if result.get("name") == options.stage_name:
                    return result
            return {}

    async def get_paginated_resources(
        self, options: PaginatedCodePipelineStageRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodePipeline stages across all pipelines in a region."""
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
                        GetPipelineStagesInput(
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
