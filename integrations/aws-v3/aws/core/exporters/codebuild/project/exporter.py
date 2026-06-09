from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codebuild.project.actions import CodeBuildProjectActionsMap
from aws.core.exporters.codebuild.project.models import CodeBuildProject
from aws.core.exporters.codebuild.project.models import (
    SingleCodeBuildProjectRequest,
    PaginatedCodeBuildProjectRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeBuildProjectExporter(IResourceExporter):
    _service_name: SupportedServices = "codebuild"
    _model_cls: Type[CodeBuildProject] = CodeBuildProject
    _actions_map: Type[CodeBuildProjectActionsMap] = CodeBuildProjectActionsMap

    async def get_resource(
        self, options: SingleCodeBuildProjectRequest
    ) -> dict[str, Any]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [options.project_name], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedCodeBuildProjectRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_projects", "projects")

            async for projects in paginator.paginate(batch_size=100):
                if projects:
                    action_result = await inspector.inspect(
                        projects,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
