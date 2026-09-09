from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.pipeline.actions import (
    PipelineActionsMap,
    CodePipelinePipelineActionInput,
)
from aws.core.exporters.codepipeline.pipeline.models import Pipeline
from aws.core.exporters.codepipeline.pipeline.models import (
    SinglePipelineRequest,
    PaginatedPipelineRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class PipelineExporter(IResourceExporter[CodePipelinePipelineActionInput]):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[Pipeline] = Pipeline
    _actions_map: Type[PipelineActionsMap] = PipelineActionsMap

    async def get_resource(self, options: SinglePipelineRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodePipeline pipeline."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single-pipeline fetch only has a pipeline name from CloudTrail.
            # Confirm it exists so a missing pipeline raises and the live-event handler
            # can treat a stale update as delete instead of upserting an empty stub.
            await proxy.client.get_pipeline(name=options.pipeline_name)  # type: ignore[attr-defined]

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                CodePipelinePipelineActionInput(
                    items=[{"name": options.pipeline_name}],
                    region=options.region,
                    account_id=options.account_id,
                ),
                options.include,
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedPipelineRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodePipeline pipelines in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
                action_id_key="name",
            )

            paginator = proxy.get_paginator("list_pipelines", "pipelines")

            async for pipelines in paginator.paginate():
                if pipelines:
                    action_result = await inspector.inspect(
                        CodePipelinePipelineActionInput(
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
