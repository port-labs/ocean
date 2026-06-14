from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codebuild.build_run.actions import (
    BuildRunActionsMap,
)
from aws.core.exporters.codebuild.build_run.models import BuildRun
from aws.core.exporters.codebuild.build_run.models import (
    SingleBuildRunRequest,
    PaginatedBuildRunRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeBuildBuildRunExporter(IResourceExporter):
    _service_name: SupportedServices = "codebuild"
    _model_cls: Type[BuildRun] = BuildRun
    _actions_map: Type[BuildRunActionsMap] = BuildRunActionsMap

    async def get_resource(self, options: SingleBuildRunRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single build run."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect([options.build_id], options.include)
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedBuildRunRequest
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
                        builds,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                else:
                    yield []
