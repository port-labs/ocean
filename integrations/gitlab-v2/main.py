from typing import cast, Any, Dict

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
)
import asyncio
from gitlab.clients.client_factory import create_gitlab_client
from gitlab.helpers.utils import ObjectKind
from integration import (
    GitLabFilesResourceConfig,
    ProjectResourceConfig,
    GitLabFoldersResourceConfig,
    GitlabGroupWithMembersResourceConfig,
    GitlabMemberResourceConfig,
    GitlabMergeRequestResourceConfig,
)

from gitlab.webhook.webhook_processors.merge_request_webhook_processor import (
    MergeRequestWebhookProcessor,
)
from gitlab.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from gitlab.webhook.webhook_processors.group_webhook_processor import (
    GroupWebhookProcessor,
)
from gitlab.webhook.webhook_factory.group_webhook_factory import GroupWebHook
from gitlab.webhook.webhook_processors.push_webhook_processor import (
    PushWebhookProcessor,
)
from gitlab.webhook.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
)
from gitlab.webhook.webhook_processors.job_webhook_processor import (
    JobWebhookProcessor,
)
from gitlab.webhook.webhook_processors.member_webhook_processor import (
    MemberWebhookProcessor,
)
from gitlab.webhook.webhook_processors.group_with_member_webhook_processor import (
    GroupWithMemberWebhookProcessor,
)
from gitlab.webhook.webhook_processors.file_push_webhook_processor import (
    FilePushWebhookProcessor,
)
from gitlab.webhook.webhook_processors.folder_push_webhook_processor import (
    FolderPushWebhookProcessor,
)


RESYNC_GROUP_MEMBERS_BATCH_SIZE = 10


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean GitLab-v2 Integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if base_url := ocean.app.base_url:
        logger.info(f"Creating webhooks for all groups at {base_url}")
        client = create_gitlab_client()
        webhook_factory = GroupWebHook(client, base_url)
        await webhook_factory.create_webhooks_for_all_groups()


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(ProjectResourceConfig, event.resource_config).selector

    include_languages = bool(selector.include_languages)

    async for projects_batch in client.get_projects(
        include_languages=include_languages
    ):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        yield projects_batch


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Received group batch with {len(groups_batch)} groups")
        yield groups_batch


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Processing batch of {len(groups_batch)} groups for issues")
        async for issues_batch in client.get_groups_resource(groups_batch, "issues"):
            yield issues_batch


@ocean.on_resync(ObjectKind.PIPELINE)
async def on_resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for projects_batch in client.get_projects():
        logger.info(f"Processing batch of {len(projects_batch)} projects for pipelines")
        async for pipelines_batch in client.get_projects_resource(
            projects_batch, "pipelines"
        ):
            yield pipelines_batch


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Limit the number of jobs that are yielded to 100.
    Results will be approximately 100 (more or less).
    """
    client = create_gitlab_client()

    async for projects_batch in client.get_projects():
        logger.info(f"Processing batch of {len(projects_batch)} projects for jobs")
        async for jobs_batch in client.get_pipeline_jobs(projects_batch):
            yield jobs_batch


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitlabMergeRequestResourceConfig, event.resource_config).selector

    states = selector.states
    updated_after = selector.updated_after_datetime

    async for groups_batch in client.get_groups():
        for state in states:
            logger.info(
                f"Processing batch of {len(groups_batch)} groups for {state} merge requests"
                + (f" updated after {updated_after}" if state != "opened" else "")
            )
            params: Dict[str, Any] = {"state": state}
            if state != "opened":
                params["updated_after"] = updated_after

            async for merge_requests_batch in client.get_groups_resource(
                groups_batch, "merge_requests", params=params
            ):
                yield merge_requests_batch


@ocean.on_resync(ObjectKind.GROUP_WITH_MEMBERS)
async def on_resync_groups_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(
        GitlabGroupWithMembersResourceConfig, event.resource_config
    ).selector
    include_bot_members = bool(selector.include_bot_members)

    async for groups_batch in client.get_groups():
        for i in range(0, len(groups_batch), RESYNC_GROUP_MEMBERS_BATCH_SIZE):
            current_batch = groups_batch[i : i + RESYNC_GROUP_MEMBERS_BATCH_SIZE]
            logger.info(
                f"Processing members for {i + len(current_batch)}/{len(groups_batch)} groups"
            )

            tasks = [
                client.enrich_group_with_members(group, include_bot_members)
                for group in current_batch
            ]
            results = await asyncio.gather(*tasks)
            yield results


@ocean.on_resync(ObjectKind.MEMBER)
async def on_resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitlabMemberResourceConfig, event.resource_config).selector
    include_bot_members = bool(selector.include_bot_members)

    async for groups_batch in client.get_groups():
        for i in range(0, len(groups_batch), RESYNC_GROUP_MEMBERS_BATCH_SIZE):
            current_batch = groups_batch[i : i + RESYNC_GROUP_MEMBERS_BATCH_SIZE]
            tasks = [
                client.get_group_members(group["id"], include_bot_members)
                for group in current_batch
            ]
            async for batch in stream_async_iterators_tasks(*tasks):
                if batch:
                    yield batch


@ocean.on_resync(ObjectKind.FILE)
async def on_resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(GitLabFilesResourceConfig, event.resource_config).selector

    search_path = selector.files.path
    scope = "blobs"
    skip_parsing = selector.files.skip_parsing

    repositories = (
        selector.files.repos
        if hasattr(selector.files, "repos") and selector.files.repos
        else None
    )

    async for files_batch in client.search_files(
        scope, search_path, repositories, skip_parsing
    ):
        yield await client._enrich_files_with_repos(files_batch)


@ocean.on_resync(ObjectKind.FOLDER)
async def on_resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitLabFoldersResourceConfig, event.resource_config).selector

    for folder_selector in selector.folders:
        path = folder_selector.path
        repos = folder_selector.repos

        if not repos:
            logger.info(
                f"No repositories specified for path {path}; skipping folder resync"
            )
            continue

        for repo in repos:
            async for folders_batch in client.get_repository_folders(
                path=path, repository=repo.name, branch=repo.branch
            ):
                logger.info(f"Found batch of {len(folders_batch)} matching folders")
                yield folders_batch


ocean.add_webhook_processor("/hook/{group_id}", GroupWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", MergeRequestWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", IssueWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", PushWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", PipelineWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", JobWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", MemberWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", GroupWithMemberWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", FilePushWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", FolderPushWebhookProcessor)
