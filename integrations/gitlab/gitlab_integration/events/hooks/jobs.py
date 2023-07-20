from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Job(HookHandler):
    events = ["Job Hook"]

    async def _on_hook(
        self, group_id: str, body: dict[str, Any], gitlab_project: Project
    ) -> None:
        job = gitlab_project.jobs.get(body["object_attributes"]["iid"])
        await ocean.register_raw(ObjectKind.JOB, [job.asdict()])
