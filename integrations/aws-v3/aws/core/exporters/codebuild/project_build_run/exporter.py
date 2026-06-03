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

            try:
                # List all builds using list_builds API
                # CodeBuild doesn't have a direct paginator for all builds, so we'll use list_builds
                response = await proxy.client.list_builds(sortOrder='DESCENDING')
                build_ids = response.get('ids', [])
                
                if not build_ids:
                    logger.info("No build runs found in region")
                    yield []
                    return

                # Process builds in batches (batch_get_builds supports up to 100 at a time)
                batch_size = 100
                for i in range(0, len(build_ids), batch_size):
                    batch_ids = build_ids[i:i + batch_size]
                    
                    # Convert to expected format for inspector
                    batch_resources = [{"id": build_id} for build_id in batch_ids]
                    
                    if batch_resources:
                        action_result = await inspector.inspect(
                            batch_resources,
                            options.include,
                            extra_context={
                                "AccountId": options.account_id,
                                "Region": options.region,
                            },
                        )
                        
                        # Filter by project name if specified
                        if options.project_name:
                            filtered_result = [
                                result for result in action_result
                                if result.get("Properties", {}).get("ProjectName") == options.project_name
                            ]
                            yield filtered_result
                        else:
                            yield action_result
                    else:
                        yield []

            except Exception as e:
                logger.error(f"Error fetching CodeBuild project build runs: {e}")
                yield []