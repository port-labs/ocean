import typing
from typing import Any
from enum import StrEnum

from loguru import logger
from gitlab.v4.objects import Project

from gitlab_integration.core.utils import generate_ref, does_pattern_apply
from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.git_integration import GitlabPortAppConfig
from gitlab_integration.utils import ObjectKind

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean


class FileAction(StrEnum):
    REMOVED = "removed"
    ADDED = "added"
    MODIFIED = "modified"


class PushHook(ProjectHandler):
    events = ["Push Hook"]
    system_events = ["push"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        logger.debug(
            f"Handling push hook for project {gitlab_project.path_with_namespace}, ref: {body.get('ref')}, commit_id: {body.get('after')}"
        )
        commit_before, commit_after, ref = (
            body.get("before"),
            body.get("after"),
            body.get("ref"),
        )

        if commit_before is None or commit_after is None or ref is None:
            raise ValueError(
                "Invalid push hook. Missing one or more of the required fields (before, after, ref)"
            )

        added_files = [
            added_file
            for commit in body.get("commits", [])
            for added_file in commit.get(FileAction.ADDED, [])
        ]
        modified_files = [
            modified_file
            for commit in body.get("commits", [])
            for modified_file in commit.get(FileAction.MODIFIED, [])
        ]

        removed_files = [
            removed_file
            for commit in body.get("commits", [])
            for removed_file in commit.get(FileAction.REMOVED, [])
        ]

        config: GitlabPortAppConfig = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        )

        branch = config.branch or gitlab_project.default_branch

        if generate_ref(branch) == ref:
            spec_path = config.spec_path
            if not isinstance(spec_path, list):
                spec_path = [spec_path]

            await self._process_files(
                gitlab_project,
                removed_files,
                spec_path,
                commit_before,
                "",
                branch,
                FileAction.REMOVED,
            )
            await self._process_files(
                gitlab_project,
                added_files,
                spec_path,
                "",
                commit_after,
                branch,
                FileAction.ADDED,
            )
            await self._process_files(
                gitlab_project,
                modified_files,
                spec_path,
                commit_before,
                commit_after,
                branch,
                FileAction.MODIFIED,
            )

            # update information regarding the project as well
            logger.info(
                f"Updating project information after push hook for project {gitlab_project.path_with_namespace}"
            )
            enriched_project = await self.gitlab_service.enrich_project_with_extras(
                gitlab_project
            )
            await ocean.register_raw(ObjectKind.PROJECT, [enriched_project])

        else:
            logger.debug(
                f"Skipping push hook for project {gitlab_project.path_with_namespace} because the ref {ref} "
                f"does not match the branch {branch}"
            )

    async def _process_files(
        self,
        gitlab_project: Project,
        files: list[str],
        spec_path: list[str],
        commit_before: str,
        commit_after: str,
        branch: str,
        file_action: FileAction,
    ) -> None:
        if not files:
            return
        logger.info(
            f"Processing {file_action} files {files} for project {gitlab_project.path_with_namespace}"
        )
        matching_files = [file for file in files if does_pattern_apply(spec_path, file)]

        if not matching_files:
            logger.info("No matching files found for mapping")
            logger.debug(f"Files {files} didn't match {spec_path} patten")
            return
        else:
            logger.info(
                f"While processing {file_action} Found {len(matching_files)} that matches {spec_path}, matching files: {matching_files}"
            )

            for file in matching_files:
                try:
                    match file_action:
                        case FileAction.REMOVED:
                            entities_before = (
                                await self.gitlab_service._get_entities_by_commit(
                                    gitlab_project, file, commit_before, branch
                                )
                            )
                            await ocean.update_diff(
                                {"before": entities_before, "after": []},
                                UserAgentType.gitops,
                            )

                        case FileAction.ADDED:
                            entities_after = (
                                await self.gitlab_service._get_entities_by_commit(
                                    gitlab_project, file, commit_after, branch
                                )
                            )
                            await ocean.update_diff(
                                {"before": [], "after": entities_after},
                                UserAgentType.gitops,
                            )

                        case FileAction.MODIFIED:
                            entities_before = (
                                await self.gitlab_service._get_entities_by_commit(
                                    gitlab_project, file, commit_before, branch
                                )
                            )
                            entities_after = (
                                await self.gitlab_service._get_entities_by_commit(
                                    gitlab_project, file, commit_after, branch
                                )
                            )
                            await ocean.update_diff(
                                {"before": entities_before, "after": entities_after},
                                UserAgentType.gitops,
                            )
                except Exception as e:
                    logger.error(
                        f"Error processing file {file} in action {file_action}: {str(e)}"
                    )
            skipped_files = set(files) - set(matching_files)
            logger.debug(
                f"Skipped {len(skipped_files)} files as they didn't match {spec_path} Skipped files: {skipped_files}"
            )
