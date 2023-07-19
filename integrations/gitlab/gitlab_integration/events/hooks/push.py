import typing
from typing import Any

from gitlab_integration.core.utils import generate_ref
from gitlab_integration.custom_integration import GitlabPortAppConfig
from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.models import HookContext, ObjectKind
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean


class PushHook(HookHandler):
    events = ["Push Hook"]

    async def _on_hook(self, group_id: str, body: dict[str, Any]) -> None:
        context = HookContext(**body)
        config: GitlabPortAppConfig = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        )

        if generate_ref(config.branch) != context.ref:
            return

        _, entities_after = self.gitlab_service.get_entities_diff(
            context, config.spec_path, context.before, context.after, config.branch
        )
        await ocean.sync(entities_after, UserAgentType.gitops)

        projects = self.gitlab_service.get_project(context.project.id)
        await ocean.register_raw(ObjectKind.PROJECT, projects)
