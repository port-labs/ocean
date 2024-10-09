from typing import Any

from loguru import logger
from gitlab.v4.objects import Project

from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Job(ProjectHandler):
    events = ["Job Hook"]
    system_events = ["job"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        logger.info(
            f"Handling job hook for project {gitlab_project.path_with_namespace}, job_id: {body.get('build_id')},"
            f" job_name: {body.get('build_name')}, status: {body.get('build_status')}"
        )
        job = await AsyncFetcher.fetch_single(gitlab_project.jobs.get, body["build_id"])
        await ocean.register_raw(ObjectKind.JOB, [job.asdict()])
