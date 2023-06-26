from gitlabapp.events.hooks.base import HookHandler
from gitlabapp.models.gitlab import HookContext
from starlette.requests import Request

from port_ocean.context.ocean import ocean


class Issues(HookHandler):
    events = ["Issue Hook"]

    async def _on_hook(self, group_id: str, request: Request) -> None:
        body = await request.json()
        project = self.gitlab_service.gitlab_client.projects.get(body["project"]["id"])

        issue = project.issues.get(body["object_attributes"]["iid"])
        await ocean.register_raw(
            "issues",
            {
                "before": [],
                "after": [issue.asdict()],
            },
        )
