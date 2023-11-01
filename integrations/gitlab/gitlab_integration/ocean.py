import asyncio
import typing
from datetime import datetime, timedelta
from typing import Any, Literal

from loguru import logger
from starlette.requests import Request
from port_ocean.context.event import event

from gitlab_integration.bootstrap import event_handler
from gitlab_integration.bootstrap import setup_application
from gitlab_integration.git_integration import GitlabResourceConfig
from gitlab_integration.utils import ObjectKind, get_cached_all_services
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

NO_WEBHOOK_WARNING = "Without setting up the webhook, the integration will not export live changes from the gitlab"


@ocean.router.post("/hook/{group_id}")
async def handle_webhook(group_id: str, request: Request) -> dict[str, Any]:
    event_id = f'{request.headers.get("X-Gitlab-Event")}:{group_id}'
    body = await request.json()
    await event_handler.notify(event_id, group_id, body)
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    logic_settings = ocean.integration_config
    if not logic_settings.get("app_host"):
        logger.warning(
            f"No app host provided, skipping webhook creation. {NO_WEBHOOK_WARNING}"
        )
        return

    try:
        setup_application(
            logic_settings["token_mapping"],
            logic_settings["gitlab_host"],
            logic_settings["app_host"],
        )
    except Exception as e:
        logger.warning(
            f"Failed to setup webhook: {e}. {NO_WEBHOOK_WARNING}",
            stack_info=True,
        )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        masked_token = len(str(service.gitlab_client.private_token)[:-4]) * "*"
        logger.info(f"fetching projects for token {masked_token}")
        async for projects_batch in service.get_all_projects():
            logger.info(f"Fetching extras for {len(projects_batch)} projects")
            tasks = []
            for project in projects_batch:
                tasks.append(service.enrich_project_with_extras(project))
            projects = await asyncio.gather(*tasks)
            logger.info(f"Finished fetching extras for {len(projects_batch)} projects")
            yield projects


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        gitlab_resource_config: GitlabResourceConfig = typing.cast(
            "GitlabResourceConfig", event.resource_config
        )
        if not isinstance(gitlab_resource_config, GitlabResourceConfig):
            return
        selector = gitlab_resource_config.selector
        async for projects_batch in service.get_all_projects():
            for folder_selector in selector.folders:
                for project in projects_batch:
                    if project.name in folder_selector.repos:
                        async for folders_batch in service.get_all_folders_in_project_path(
                            project, folder_selector
                        ):
                            yield folders_batch


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    updated_after = datetime.now() - timedelta(days=14)

    for service in get_cached_all_services():
        for group in service.get_root_groups():
            async for merge_request_batch in service.get_opened_merge_requests(group):
                yield [merge_request.asdict() for merge_request in merge_request_batch]
            async for merge_request_batch in service.get_closed_merge_requests(
                group, updated_after
            ):
                yield [merge_request.asdict() for merge_request in merge_request_batch]


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        for group in service.get_root_groups():
            async for issues_batch in service.get_all_issues(group):
                yield [issue.asdict() for issue in issues_batch]


@ocean.on_resync(ObjectKind.JOB)
async def resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for projects_batch in service.get_all_projects():
            for project in projects_batch:
                async for jobs_batch in service.get_all_jobs(project):
                    yield [job.asdict() for job in jobs_batch]


@ocean.on_resync(ObjectKind.PIPELINE)
async def resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for projects_batch in service.get_all_projects():
            for project in projects_batch:
                logger.info(
                    f"Fetching pipelines for project {project.path_with_namespace}"
                )
                async for pipelines_batch in service.get_all_pipelines(project):
                    logger.info(
                        f"Found {len(pipelines_batch)} pipelines for project {project.path_with_namespace}"
                    )
                    yield [
                        {**pipeline.asdict(), "__project": project.asdict()}
                        for pipeline in pipelines_batch
                    ]
