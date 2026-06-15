from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codepipeline.action.actions import CodePipelineActionActionsMap, CodePipelinePipelineActionInput
from aws.core.exporters.codepipeline.action.models import CodePipelineAction
from aws.core.exporters.codepipeline.action.models import (
    SingleCodePipelineActionRequest,
    PaginatedCodePipelineActionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodePipelineActionExporter(IResourceExporter[CodePipelinePipelineActionInput]):
    _service_name: SupportedServices = "codepipeline"
    _model_cls: Type[CodePipelineAction] = CodePipelineAction
    _actions_map: Type[CodePipelineActionActionsMap] = CodePipelineActionActionsMap

    async def get_resource(self, options: SingleCodePipelineActionRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodePipeline action."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            # For single action, we need to get the specific pipeline and extract the action
            response = await inspector.inspect(
                CodePipelinePipelineActionInput(items=[{'name': options.pipeline_name}],
                                                region=options.region,
                                                account_id=options.account_id),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                    "TargetStageName": options.stage_name,
                    "TargetActionName": options.action_name,
                },
            )

            # Filter the response to get only the requested action
            if response:
                for action in response:
                    if (action.get("Properties", {}).get("StageName") == options.stage_name and
                        action.get("Properties", {}).get("ActionName") == options.action_name):
                        return action

            return {}

    async def get_paginated_resources(
        self, options: PaginatedCodePipelineActionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
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
                        CodePipelinePipelineActionInput(items=pipelines, region=options.region, account_id=options.account_id),
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
