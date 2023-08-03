from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class MergeRequest(HookHandler):
    events = ["Merge Request Hook"]

    async def _on_hook(
        self, group_id: str, body: dict[str, Any], gitlab_project: Project
    ) -> None:
        merge_requests = gitlab_project.mergerequests.get(
            body["object_attributes"]["id"]
        )
        await ocean.register_raw(ObjectKind.MERGE_REQUEST, [merge_requests.asdict()])
