from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from starlette.requests import Request

from gitlab_integration.bootstrap import event_handler
from gitlab_integration.bootstrap import setup_application
from gitlab_integration.utils import get_all_services, ObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import RAW_RESULT, ASYNC_GENERATOR_RESYNC_TYPE

NO_WEBHOOK_WARNING = "Without setting up the webhook, the integration will not export live changes from the gitlab"

all_tokens_services = get_all_services()


@ocean.router.post("/hook/{group_id}")
async def handle_webhook(group_id: str, request: Request) -> dict[str, Any]:
    event_id = f'{request.headers.get("X-Gitlab-Event")}:{group_id}'
    body = await request.json()
    await event_handler.notify(event_id, group_id, body)
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logic_settings = ocean.integration_config
    if not logic_settings.get("app_host"):
        logger.warning(
            f"No app host provided, skipping webhook creation. {NO_WEBHOOK_WARNING}"
        )
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
async def on_resync(kind: str) -> RAW_RESULT:
    projects = []

    for service in all_tokens_services:
        masked_token = len(str(service.gitlab_client.private_token)[:-4]) * "*"
        logger.info(f"fetching projects for token {masked_token}")
        result = [project.asdict() for project in service.get_all_projects().values()]
        logger.info(f"found {len(result)} projects")
        projects.extend(result)

    return projects


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_requests(kind: str) -> RAW_RESULT:
    updated_after = datetime.now() - timedelta(days=14)

    result = []
    for service in all_tokens_services:
        for group in service.get_root_groups():
            merge_requests = group.mergerequests.list(
                all=True, state="opened"
            ) + group.mergerequests.list(
                all=True,
                state=["closed", "locked", "merged"],
                updated_after=updated_after.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            )
            for merge_request in merge_requests:
                project_path = merge_request.references.get("full").rstrip(
                    merge_request.references.get("short")
                )
                if service.should_run_for_project(project_path):
                    result.append(merge_request.asdict())
    return result


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
        for project_id, project in service.get_all_projects().items():
            jobs = project.jobs.list(per_page=100)
            logger.info(f"Found {len(jobs)} jobs for project {project_id}")
            yield [job.asdict() for job in jobs]


@ocean.on_resync(ObjectKind.PIPELINE)
async def resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    from_time = datetime.now() - timedelta(days=14)
    created_after = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    for service in all_tokens_services:
        for project_id, project in service.get_all_projects().items():
            batch_size = 50
            page = 1
            more = True

            while more:
                # Process the batch of pipelines here
                pipelines = project.pipelines.list(
                    page=page, per_page=batch_size, created_after=created_after
                )
                logger.info(
                    f"Found {len(pipelines)} pipelines for page number {page} in project {project_id}"
                )
                yield [
                    {
                        **pipeline.asdict(),
                        "__project": project.asdict(),
                    }
                    for pipeline in pipelines
                ]

                # Fetch the next batch
                page += 1
                more = len(pipelines) == batch_size
