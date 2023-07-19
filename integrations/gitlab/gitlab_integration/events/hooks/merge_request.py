from starlette.requests import Request

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.models import ObjectKind
from port_ocean.context.ocean import ocean


class MergeRequest(HookHandler):
    events = ["Merge Request Hook"]

    async def _on_hook(self, group_id: str, request: Request) -> None:
        body = await request.json()
        project = self.gitlab_service.gitlab_client.projects.get(body["project"]["id"])

        merge_requests = project.mergerequests.get(body["object_attributes"]["iid"])
        await ocean.register_raw(ObjectKind.MERGE_REQUEST, [merge_requests.asdict()])
