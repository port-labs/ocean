from typing import Any, Dict

from gitlab_integration.bootstrap import event_handler
from gitlab_integration.bootstrap import setup_application
from gitlab_integration.utils import get_all_services, ObjectKind
from loguru import logger
from starlette.requests import Request

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import RAW_RESULT, ASYNC_GENERATOR_RESYNC_TYPE

all_tokens_services = get_all_services()


@ocean.router.post("/hook/{group_id}")
async def handle_webhook(group_id: str, request: Request) -> Dict[str, Any]:
    event_id = f'{request.headers.get("X-Gitlab-Event")}:{group_id}'
    body = await request.json()
    await event_handler.notify(event_id, group_id, body)
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    setup_application()


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync(kind: str) -> RAW_RESULT:
    projects = []

    for service in all_tokens_services:
        logger.info(
            f"fetching projects for token {service.gitlab_client.private_token}"
        )
        result = [project.asdict() for project in service.get_all_projects()]
        logger.info(f"found {len(result)} projects")
        projects.extend(result)

    return projects


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_requests(kind: str) -> RAW_RESULT:
    merge_requests = []
    for service in all_tokens_services:
        for group in service.get_root_groups():
            for merge_request in group.mergerequests.list(all=True):
                project_path = merge_request.references.get("full").rstrip(
                    merge_request.references.get("short")
                )
                if service.should_run_for_project(project_path):
                    merge_requests.append(merge_request.asdict())
    return merge_requests


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> RAW_RESULT:
    issues = []
    for service in all_tokens_services:
        for group in service.get_root_groups():
            for issue in group.issues.list(all=True):
                project_path = issue.references.get("full").rstrip(
                    issue.references.get("short")
                )
                if service.should_run_for_project(project_path):
                    issues.append(issue.asdict())
    return issues


@ocean.on_resync(ObjectKind.JOB)
async def resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in all_tokens_services:
        for project in service.get_all_projects():
            jobs = project.jobs.list(per_page=100)
            logger.info(f"Found {len(jobs)} jobs for project {project.id}")
            for job in jobs:
                yield job.asdict()


@ocean.on_resync(ObjectKind.PIPELINE)
async def resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in all_tokens_services:
        for project in service.get_all_projects():
            pipelines = project.pipelines.list(all=True)
            logger.info(f"Found {len(pipelines)} pipelines for project {project.id}")
            for pipeline in pipelines:
                yield pipeline.asdict()
