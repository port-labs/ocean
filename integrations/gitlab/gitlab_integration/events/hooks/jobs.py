from typing import Any

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.models import ObjectKind
from port_ocean.context.ocean import ocean


class Job(HookHandler):
    events = ["Job Hook"]

    async def _on_hook(self, group_id: str, body: dict[str, Any]) -> None:
        project = self.gitlab_service.gitlab_client.projects.get(body["project"]["id"])

        job = project.jobs.get(body["object_attributes"]["iid"])
        await ocean.register_raw(ObjectKind.JOB, [job.asdict()])
