from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Job(ProjectHandler):
    events = ["Job Hook"]
    system_events = ["job"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        with ThreadPoolExecutor() as executor:
            job = await get_event_loop().run_in_executor(
                executor, gitlab_project.jobs.get, body["build_id"]
            )
        await ocean.register_raw(ObjectKind.JOB, [job.asdict()])
