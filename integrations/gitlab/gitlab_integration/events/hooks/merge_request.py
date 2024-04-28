import asyncio
from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class MergeRequest(ProjectHandler):
    events = ["Merge Request Hook"]
    system_events = ["merge_request"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        with ThreadPoolExecutor() as executor:
            merge_requests = await get_event_loop().run_in_executor(
                executor,
                gitlab_project.mergerequests.get,
                body["object_attributes"]["iid"],
            )
        await ocean.register_raw(ObjectKind.MERGE_REQUEST, [merge_requests.asdict()])
