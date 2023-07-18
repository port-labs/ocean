from typing import Any, Dict, List

from gitlab.base import RESTObject
from loguru import logger
from starlette.requests import Request

from gitlab_integration.bootstrap import setup_application
from gitlab_integration.events.event_handler import EventHandler
from gitlab_integration.utils import get_all_services
from port_ocean.context.ocean import ocean


@ocean.router.post("/hook/{group_id}")
async def handle_webhook(group_id: str, request: Request) -> Dict[str, Any]:
    event_id = f'{request.headers.get("X-Gitlab-Event")}:{group_id}'
    await request.json()
    await EventHandler().notify(event_id, group_id, request)
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    setup_application()


@ocean.on_resync("project")
async def on_resync(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    projects = []

    for service in all_tokens_services:
        logger.info(
            f"fetching projects for token {service.gitlab_client.private_token}"
        )
        projects.extend(service.get_projects_by_scope())

    return projects


@ocean.on_resync("mergeRequest")
async def resync_merge_requests(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    root_groups: list[RESTObject] = sum(
        [service.get_root_groups() for service in all_tokens_services], []
    )
    return [
        merge_request.asdict()
        for group in root_groups
        for merge_request in group.mergerequests.list(scope="all", all=True)
    ]


@ocean.on_resync("issues")
async def resync_issues(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    root_groups: list[RESTObject] = sum(
        [service.get_root_groups() for service in all_tokens_services], []
    )
    return [issue.asdict() for group in root_groups for issue in group.issues.list()]


@ocean.on_resync("job")
async def resync_jobs(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    root_groups: list[RESTObject] = sum(
        [service.get_root_groups() for service in all_tokens_services], []
    )
    return [job.asdict() for group in root_groups for job in group.jobs.list()]


@ocean.on_resync("pipelines")
async def resync_pipelines(kind: str) -> List[Dict[Any, Any]]:
    all_tokens_services = get_all_services()
    root_groups: list[RESTObject] = sum(
        [service.get_root_groups() for service in all_tokens_services], []
    )
    return [
        pipeline.asdict()
        for group in root_groups
        for pipeline in group.pipelines.list()
    ]
