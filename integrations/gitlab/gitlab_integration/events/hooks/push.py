import typing
from typing import Any

from loguru import logger
from gitlab.v4.objects import Project

from gitlab_integration.core.utils import generate_ref, does_pattern_apply
from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.git_integration import GitlabPortAppConfig
from gitlab_integration.utils import ObjectKind

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean


class PushHook(ProjectHandler):
    events = ["Push Hook"]
    system_events = ["push"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        before, after, ref = body.get("before"), body.get("after"), body.get("ref")

        if before is None or after is None or ref is None:
            raise ValueError(
                "Invalid push hook. Missing one or more of the required fields (before, after, ref)"
            )

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

        changed_files = list(set(added_files + modified_files))

        config: GitlabPortAppConfig = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        )

        branch = config.branch or gitlab_project.default_branch

        if generate_ref(branch) == ref:
            spec_path = config.spec_path
            if not isinstance(spec_path, list):
                spec_path = [spec_path]
            await self._process_changed_files(
                gitlab_project, changed_files, spec_path, before, after, branch
            )

        else:
            logger.debug(
                f"Skipping push hook for project {gitlab_project.path_with_namespace} because the ref {ref} "
                f"does not match the branch {branch}"
            )

    async def _process_changed_files(
        self,
        gitlab_project: Project,
        changed_files: list[str],
        spec_path: list[str],
        before: str,
        after: str,
        branch: str,
    ) -> None:
        logger.info(
            f"Processing changed files {changed_files} for project {gitlab_project.path_with_namespace}"
        )

        for file in changed_files:
            if does_pattern_apply(spec_path, file):
                logger.info(
                    f"Found file {file} in spec_path {spec_path} pattern, processing its entity diff"
                )

                entities_before, entities_after = (
                    await self.gitlab_service.get_entities_diff(
                        gitlab_project, file, before, after, branch
                    )
                )

                # update the entities diff found in the `config.spec_path` file the user configured
                await ocean.update_diff(
                    {"before": entities_before, "after": entities_after},
                    UserAgentType.gitops,
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
                logger.info(
                    f"Skipping file {file} as it does not match the spec_path pattern {spec_path}"
                )
