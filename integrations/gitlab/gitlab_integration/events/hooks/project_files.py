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
from gitlab_integration.core.utils import does_pattern_apply

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


class ProjectFiles(ProjectHandler):
    events = ["Push Hook"]
    system_events = ["push"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        added_files = [
            added_file
            for commit in body.get("commits", [])
            for added_file in commit.get("added", [])
        ]
        modified_files = [
            modified_file
            for commit in body.get("commits", [])
            for modified_file in commit.get("modified", [])
        ]
        removed_files = [
            removed_file
            for commit in body.get("commits", [])
            for removed_file in commit.get("removed", [])
        ]
        changed_files = list(set(added_files + modified_files))

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
            logger.debug(
                "Could not find file kind to handle the push event"
            )
            return

        for resource_config in matching_resource_configs:
            selector = resource_config.selector
            if not (selector.files and selector.files.path):
                return

            if self.gitlab_service.should_process_project(
                gitlab_project, selector.files.repos
            ):
                matched_file_paths = self.gitlab_service._get_file_paths(
                    gitlab_project, selector.files.path, gitlab_project.default_branch
                )
                await self._process_modified_files(
                    gitlab_project, changed_files, matched_file_paths
                )
                await self._process_removed_files(
                    gitlab_project, removed_files, selector.files.path, body["before"]
                )

    async def _process_modified_files(
        self,
        gitlab_project: Project,
        modified_files: list[str],
        matched_file_paths: list[str],
    ) -> None:
        """
        Process the modified files and register them.
        """
        for modified_file in modified_files:
            if modified_file in matched_file_paths:
                file_data = self.gitlab_service.get_and_parse_single_file(
                    gitlab_project, modified_file, gitlab_project.default_branch
                )
                if file_data:
                    await ocean.register_raw(ObjectKind.FILE, [file_data])

    async def _process_removed_files(
        self, project: Project, removed_files: list[str],  selector_path: str, commit_id_before_push: str
    ) -> None:
        """
        Process unregister the removed files.
        """
        for removed_file in removed_files:
            # after a file in GitLab is deleted, we can't get it's content using the list repository tree API since it returns the current files. But we can still get the file by using the commit ID just before it was deleted.
            if does_pattern_apply(selector_path, removed_file):
                file_data = self.gitlab_service.get_and_parse_single_file(
                    project, removed_file, commit_id_before_push
                )
                if file_data:
                    await ocean.unregister_raw(
                        ObjectKind.FILE,
                        [file_data]
                    )
