from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codebuild.project_build_run.actions import ProjectBuildRunActionsMap
from aws.core.exporters.codebuild.project_build_run.models import ProjectBuildRun
from aws.core.exporters.codebuild.project_build_run.models import (
    SingleProjectBuildRunRequest,
    PaginatedProjectBuildRunRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class CodeBuildProjectBuildRunExporter(IResourceExporter):
    _service_name: SupportedServices = "codebuild"
    _model_cls: Type[ProjectBuildRun] = ProjectBuildRun
    _actions_map: Type[ProjectBuildRunActionsMap] = ProjectBuildRunActionsMap

    async def get_resource(self, options: SingleProjectBuildRunRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single build run."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"id": options.build_id}], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedProjectBuildRunRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all build runs in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_builds", "ids")
            async for builds in paginator.paginate(batch_size=100):
                if builds:
                    yield await inspector.inspect(
                        [{"id": build_id} for build_id in builds],
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                else:
                    yield []
