from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Issues(HookHandler):
    events = ["Issue Hook"]
    system_events = ["issue"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        issue = gitlab_project.issues.get(body["object_attributes"]["id"])
        await ocean.register_raw(ObjectKind.ISSUE, [issue.asdict()])
