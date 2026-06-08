import json
from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.pipeline.actions import PipelineActionsMap
from aws.core.exporters.codepipeline.pipeline.models import (
    Pipeline,
    CodePipelineStage,
    CodePipelineStageProperties,
)
from aws.core.exporters.codepipeline.pipeline.models import (
    SinglePipelineRequest,
    PaginatedPipelineRequest,
)
from aws.core.helpers.types import SupportedServices, ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from aws.core.modeling.resource_models import ResourceRequestModel


class PipelineExporter(IResourceExporter):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[Pipeline] = Pipeline
    _actions_map: Type[PipelineActionsMap] = PipelineActionsMap

    async def get_resource(self, options: SinglePipelineRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodePipeline pipeline."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"name": options.pipeline_name}], options.include
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
                        child_builders=[self._construct_stages],
                    )
                    yield action_result
                else:
                    yield []

    def _construct_stages(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        extra_context = ResourceRequestModel(**data["__ExtraContext"],
                                             region=data['__ExtraContext']['Region'],
                                             account_id=data['__ExtraContext']['AccountId'])
        return [
            json.loads(
                CodePipelineStage(
                    Properties=CodePipelineStageProperties(
                        Name=stage.get("name"),
                        PipelineName=data["Properties"].get("Name"),
                        PipelineArn=data["Properties"].get("Arn"),
                        Actions=stage.get("actions", []),
                        Blockers=stage.get("blockers", []),
                        Region=extra_context.region,
                        AccountId=extra_context.account_id,
                    ),
                    __ExtraContext=extra_context,
                ).json(by_alias=True)
            ) | {'_portOceanKind': ObjectKind.CODEPIPELINE_STAGE}
            for stage in data["Properties"].get("Stages", [])
        ]
