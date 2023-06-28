from starlette.requests import Request

from gitlabapp.events.hooks.base import HookHandler
from port_ocean.context.ocean import ocean


class MergeRequest(HookHandler):
    events = ["Merge Request Hook"]

    async def _on_hook(self, group_id: str, request: Request) -> None:
        body = await request.json()
        project = self.gitlab_service.gitlab_client.projects.get(body["project"]["id"])

        merge_requests = project.mergerequests.get(body["object_attributes"]["iid"])
        await ocean.register_raw("mergeRequest", [merge_requests.asdict()])
