import typing
from typing import Any

from loguru import logger
from gitlab.v4.objects import Project

from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.core.utils import generate_ref
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

        config: GitlabPortAppConfig = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        )

        branch = config.branch or gitlab_project.default_branch

        if generate_ref(branch) == ref:
            entities_before, entities_after = await AsyncFetcher.fetch_entities_diff(
                self.gitlab_service,
                gitlab_project,
                config.spec_path,
                before,
                after,
                branch,
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
            await ocean.register_raw(ObjectKind.PROJECT, [gitlab_project.asdict()])
        else:
            logger.debug(
                f"Skipping push hook for project {gitlab_project.path_with_namespace} because the ref {ref} "
                f"does not match the branch {branch}"
            )
