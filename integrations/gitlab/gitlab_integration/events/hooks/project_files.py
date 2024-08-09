import typing
from typing import Any

from loguru import logger
from gitlab.v4.objects import Project
from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.git_integration import (
    GitLabFilesResourceConfig,
    GitlabPortAppConfig,
)
from gitlab_integration.utils import ObjectKind

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


class ProjectFiles(ProjectHandler):
    events = ["Push Hook"]
    system_events = ["push"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        before, after, ref = body.get("before"), body.get("after"), body.get("ref")

        if before is None or after is None or ref is None:
            raise ValueError(
                "Invalid push hook. Missing one or more of the required fields (before, after, ref)"
            )

        resource_configs = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        ).resources

        matching_resource_configs = [
            resource_config
            for resource_config in resource_configs
            if (
                resource_config.kind == ObjectKind.FILE
                and isinstance(resource_config, GitLabFilesResourceConfig)
            )
        ]
        if not matching_resource_configs:
            logger.info(
                "Resource kind was not found in the config mapping, please update your config mapping to include the file kind"
            )
            return

        for resource_config in matching_resource_configs:
            selector = resource_config.selector
            if not (selector.files and selector.files.path):
                return

            if self.gitlab_service.should_process_project(
                gitlab_project, selector.files.repos
            ):
                async for files_batch in self.gitlab_service.get_all_files_in_project(
                    gitlab_project, selector.files.path
                ):
                    await ocean.register_raw(ObjectKind.FILE, files_batch)
