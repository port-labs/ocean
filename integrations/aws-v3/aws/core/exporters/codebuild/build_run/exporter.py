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
from aws.core.helpers.utils import require_aws_resource
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeBuildBuildRunExporter(IResourceExporter[list[str]]):
    _service_name: SupportedServices = "codebuild"
    _model_cls: Type[BuildRun] = BuildRun
    _actions_map: Type[BuildRunActionsMap] = BuildRunActionsMap

    async def get_resource(self, options: SingleBuildRunRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single build run."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single-build fetch only has a build id from CloudTrail.
            # batch_get_builds omits missing builds instead of erroring. Confirm
            # it exists so the live-event handler can treat a stale update as delete.
            batch_response = await proxy.client.batch_get_builds(  # type: ignore[attr-defined]
                ids=[options.build_id]
            )
            require_aws_resource(
                batch_response.get("builds"),
                error_code="ResourceNotFoundException",
                message=f"Build not found: {options.build_id}",
                operation_name="BatchGetBuilds",
            )

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [options.build_id],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
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
