import typing
from typing import Any

from gitlab.v4.objects import Project
from gitlab_integration.core.utils import generate_ref
from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.git_integration import GitlabPortAppConfig
from gitlab_integration.utils import ObjectKind

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean


class PushHook(HookHandler):
    events = ["Push Hook"]

    async def _on_hook(
        self, group_id: str, body: dict[str, Any], gitlab_project: Project
    ) -> None:
        before, after, ref = body.get("before"), body.get("after"), body.get("ref")

        if before is None or after is None or ref is None:
            raise ValueError(
                "Invalid push hook. Missing one or more of the required fields (before, after, ref)"
            )

        config: GitlabPortAppConfig = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        )

        if generate_ref(config.branch) == ref:
            entities_before, entities_after = self.gitlab_service.get_entities_diff(
                gitlab_project,
                config.spec_path,
                before,
                after,
                config.branch,
            )
            # Todo: implement update_diff, the sync method will not serve the purpose of updating the diff. it will delete unrelated entities2
            # await ocean.update_raw_diff()
            await ocean.sync(entities_after, UserAgentType.gitops)

        await ocean.register_raw(ObjectKind.PROJECT, [gitlab_project.asdict()])
