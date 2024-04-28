from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Issues(ProjectHandler):
    events = ["Issue Hook"]
    system_events = ["issue"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        with ThreadPoolExecutor() as executor:
            issue = await get_event_loop().run_in_executor(
                executor, gitlab_project.issues.get, body["object_attributes"]["iid"]
            )
        await ocean.register_raw(ObjectKind.ISSUE, [issue.asdict()])
