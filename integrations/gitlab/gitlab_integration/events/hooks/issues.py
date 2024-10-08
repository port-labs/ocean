from typing import Any
from loguru import logger
from gitlab.v4.objects import Project

from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.events.hooks.base import ProjectHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class Issues(ProjectHandler):
    events = ["Issue Hook"]
    system_events = ["issue"]

    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        logger.debug(
            f"Handling issue hook for project {gitlab_project.path_with_namespace}, issue_id: {body.get('object_attributes', {}).get('iid')},"
            f" issue_title: {body.get('object_attributes', {}).get('title')}, status: {body.get('object_attributes', {}).get('state')}"
        )
        issue = await AsyncFetcher.fetch_single(
            gitlab_project.issues.get, body["object_attributes"]["iid"]
        )
        await ocean.register_raw(ObjectKind.ISSUE, [issue.asdict()])
