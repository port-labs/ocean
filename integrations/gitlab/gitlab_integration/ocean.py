import asyncio
import typing
from datetime import datetime, timedelta
from itertools import islice
from typing import Any

from loguru import logger
from starlette.requests import Request

from gitlab_integration.events.setup import event_handler, system_event_handler
from gitlab_integration.models.webhook_groups_override_config import (
    WebhookMappingConfig,
)
from gitlab_integration.events.setup import setup_application
from gitlab_integration.git_integration import (
    GitlabResourceConfig,
    GitLabFilesResourceConfig,
)
from gitlab_integration.utils import ObjectKind, get_cached_all_services
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.log.sensetive import sensitive_log_filter
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

NO_WEBHOOK_WARNING = "Without setting up the webhook, the integration will not export live changes from the gitlab"
PROJECT_RESYNC_BATCH_SIZE = 10


async def start_processors() -> None:
    """Helper function to start the event processors."""
    try:
        logger.info("Starting event processors")
        await event_handler.start_event_processor()
        await system_event_handler.start_event_processor()
    except Exception as e:
        logger.exception(f"Failed to start event processors: {e}")


@ocean.router.post("/hook/{group_id}")
async def handle_webhook_request(group_id: str, request: Request) -> dict[str, Any]:
    event_id = f"{request.headers.get('X-Gitlab-Event')}:{group_id}"
    with logger.contextualize(event_id=event_id):
        try:
            logger.info(f"Received webhook event {event_id} from Gitlab")
            body = await request.json()
            await event_handler.notify(event_id, body)
            return {"ok": True}
        except Exception as e:
            logger.exception(
                f"Failed to handle webhook event {event_id} from Gitlab, error: {e}"
            )
            return {"ok": False, "error": str(e)}


@ocean.router.post("/system/hook")
async def handle_system_webhook_request(request: Request) -> dict[str, Any]:
    try:
        body: dict[str, Any] = await request.json()
        # some system hooks have event_type instead of event_name in the body, such as merge_request events
        event_name: str = str(body.get("event_name") or body.get("event_type"))
        with logger.contextualize(event_name=event_name):
            logger.info(f"Received system webhook event {event_name} from Gitlab")
            await system_event_handler.notify(event_name, body)

        return {"ok": True}
    except Exception as e:
        logger.exception(
            "Failed to handle system webhook event from Gitlab, error: {e}"
        )
        return {"ok": False, "error": str(e)}


@ocean.on_start()
async def on_start() -> None:
    integration_config = ocean.integration_config
    token_mapping: dict = integration_config["token_mapping"]
    hook_override_mapping: dict = integration_config[
        "token_group_hooks_override_mapping"
    ]
    sensitive_log_filter.hide_sensitive_strings(*token_mapping.keys())

    if hook_override_mapping is not None:
        sensitive_log_filter.hide_sensitive_strings(*hook_override_mapping.keys())

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if not integration_config.get("app_host"):
        logger.warning(
            f"No app host provided, skipping webhook creation. {NO_WEBHOOK_WARNING}. Starting the event processors"
        )
        try:
            await start_processors()
        except Exception as e:
            logger.exception(
                f"Failed to start event processors: {e}. {NO_WEBHOOK_WARNING}"
            )
        return

    token_webhook_mapping: WebhookMappingConfig | None = None

    if integration_config["token_group_hooks_override_mapping"]:
        token_webhook_mapping = WebhookMappingConfig(
            tokens=integration_config["token_group_hooks_override_mapping"]
        )

    try:
        await setup_application(
            integration_config["token_mapping"],
            integration_config["gitlab_host"],
            integration_config["app_host"],
            integration_config["use_system_hook"],
            token_webhook_mapping,
        )
    except Exception as e:
        logger.exception(f"Failed to setup webhook: {e}. {NO_WEBHOOK_WARNING}")
    try:
        await start_processors()  # Ensure event processors are started regardless of webhook setup
    except Exception as e:
        logger.exception(f"Failed to start event processors: {e}. {NO_WEBHOOK_WARNING}")


@ocean.on_resync(ObjectKind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for groups_batch in service.get_all_groups():
            yield [group.asdict() for group in groups_batch]


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        masked_token = len(str(service.gitlab_client.private_token)[:-4]) * "*"
        logger.info(f"fetching projects for token {masked_token}")
        async for projects in service.get_all_projects():
            # resync small batches of projects, so data will appear asap to the user.
            # projects takes more time than other resources as it has extra enrichment performed for each entity
            # such as languages, `file://` and `search://`
            projects_batch_iter = iter(projects)
            projects_processed_in_full_batch = 0
            while projects_batch := tuple(
                islice(projects_batch_iter, PROJECT_RESYNC_BATCH_SIZE)
            ):
                projects_processed_in_full_batch += len(projects_batch)
                logger.info(
                    f"Processing extras for {projects_processed_in_full_batch}/{len(projects)} projects in batch"
                )
                tasks = []
                for project in projects_batch:
                    tasks.append(service.enrich_project_with_extras(project))
                enriched_projects = await asyncio.gather(*tasks)
                logger.info(
                    f"Finished Processing extras for {projects_processed_in_full_batch}/{len(projects)} projects in batch"
                )
                yield enriched_projects


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
                        async for (
                            folders_batch
                        ) in service.get_all_folders_in_project_path(
                            project, folder_selector
                        ):
                            yield folders_batch


@ocean.on_resync(ObjectKind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        gitlab_resource_config: GitLabFilesResourceConfig = typing.cast(
            "GitLabFilesResourceConfig", event.resource_config
        )
        if not isinstance(gitlab_resource_config, GitLabFilesResourceConfig):
            logger.error("Invalid resource config type for GitLab files resync")
            return

        selector = gitlab_resource_config.selector

        if not (selector.files and selector.files.path):
            logger.warning("No path provided in the selector, skipping fetching files")
            return

        async for projects in service.get_all_projects():
            projects_batch_iter = iter(projects)
            projects_processed_in_full_batch = 0
            while projects_batch := tuple(
                islice(projects_batch_iter, PROJECT_RESYNC_BATCH_SIZE)
            ):
                projects_processed_in_full_batch += len(projects_batch)
                logger.info(
                    f"Processing project files for {projects_processed_in_full_batch}/{len(projects)} "
                    f"projects in batch: {[project.path_with_namespace for project in projects_batch]}"
                )
                tasks = []
                matching_projects = []
                for project in projects_batch:
                    if service.should_process_project(project, selector.files.repos):
                        matching_projects.append(project)
                        tasks.append(
                            service.search_files_in_project(
                                project, selector.files.path
                            )
                        )

                if tasks:
                    logger.info(
                        f"Found {len(tasks)} relevant projects in batch, projects: {[project.path_with_namespace for project in matching_projects]}"
                    )
                    async for batch in stream_async_iterators_tasks(*tasks):
                        yield batch
                else:
                    logger.info(
                        f"No relevant projects were found in batch for path '{selector.files.path}', skipping projects: {[project.path_with_namespace for project in projects_batch]}"
                    )
                logger.info(
                    f"Finished Processing project files for {projects_processed_in_full_batch}/{len(projects)}"
                )
        logger.info(
            f"Finished processing all projects for path '{selector.files.path}'"
        )


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    updated_after = datetime.now() - timedelta(days=14)

    for service in get_cached_all_services():
        async for groups_batch in service.get_all_root_groups():
            for group in groups_batch:
                async for merge_request_batch in service.get_opened_merge_requests(
                    group
                ):
                    yield [
                        merge_request.asdict() for merge_request in merge_request_batch
                    ]
                async for merge_request_batch in service.get_closed_merge_requests(
                    group, updated_after
                ):
                    yield [
                        merge_request.asdict() for merge_request in merge_request_batch
                    ]


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for groups_batch in service.get_all_root_groups():
            for group in groups_batch:
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
