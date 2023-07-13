from starlette.requests import Request

from gitlab_integration.core.utils import generate_ref
from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.models.gitlab import HookContext, ScopeType, Scope
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean


class PushHook(HookHandler):
    events = ["Push Hook"]

    async def _on_hook(self, group_id: str, request: Request) -> None:
        body = await request.json()
        context = HookContext(**body)
        config = event.port_app_config

        if generate_ref(config.branch) != context.ref:
            return

        _, entities_after = self.gitlab_service.get_entities_diff(
            context, config.spec_path, context.before, context.after, config.branch
        )
        await ocean.sync(entities_after, UserAgentType.gitops)

        has_changed, scope = self.gitlab_service.validate_config_changed(context)
        if has_changed:
            await ocean.sync_raw_all()

        scope = Scope(ScopeType.Project, context.project.id)
        projects = self.gitlab_service.get_projects_by_scope(scope)
        await ocean.register_raw("project", projects)
