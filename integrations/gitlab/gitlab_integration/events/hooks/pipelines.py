from typing import Any

from gitlab.v4.objects import Project

from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Pipelines(ProjectHandler):
    events = ["Pipeline Hook"]
    system_events = ["pipeline"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        pipeline = await AsyncFetcher.fetch_single(
            gitlab_project.pipelines.get, body["object_attributes"]["id"]
        )
        await ocean.register_raw(ObjectKind.PIPELINE, [pipeline.asdict()])
