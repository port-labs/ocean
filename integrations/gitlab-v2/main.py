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
from gitlab.clients.utils import build_group_params, build_project_params
from gitlab.helpers.utils import ObjectKind, enrich_resources_with_project
from integration import (
    GitLabFilesResourceConfig,
    GroupResourceConfig,
    ProjectResourceConfig,
    GitLabFoldersResourceConfig,
    GitlabGroupWithMembersResourceConfig,
    GitlabMemberResourceConfig,
    GitlabMergeRequestResourceConfig,
    PipelineResourceConfig,
    JobResourceConfig,
    ReleaseResourceConfig,
    TagResourceConfig,
    GitlabIssueResourceConfig,
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
from gitlab.webhook.webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from gitlab.webhook.webhook_processors.tag_webhook_processor import (
    TagWebhookProcessor,
)
from gitlab.webhook.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from gitlab.clients.options import IssueOptions


RESYNC_GROUP_MEMBERS_BATCH_SIZE = 10
DEFAULT_MAX_CONCURRENT = 10


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
    include_active_projects = selector.include_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(include_active_projects=include_active_projects),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=include_languages,
    ):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        yield projects_batch


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GroupResourceConfig, event.resource_config).selector
    include_active_groups = selector.include_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_active_groups=include_active_groups)
    ):
        logger.info(f"Received group batch with {len(groups_batch)} groups")
        yield groups_batch


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitlabIssueResourceConfig, event.resource_config).selector

    options: IssueOptions = IssueOptions(
        issue_type=selector.issue_type,
        labels=selector.labels,
        non_archived=selector.non_archived,
        state=selector.state,
        updated_after=(
            selector.updated_after_datetime if selector.updated_after else None
        ),
    )

    async for groups_batch in client.get_groups(
        params=build_group_params(include_active_groups=selector.include_active_groups)
    ):
        logger.info(f"Processing batch of {len(groups_batch)} groups for issues")
        params: dict[str, Any] = {
            key: value for key, value in options.items() if value is not None
        }
        async for issues_batch in client.get_groups_resource(
            groups_batch, "issues", params=params
        ):
            yield issues_batch


@ocean.on_resync(ObjectKind.PIPELINE)
async def on_resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(PipelineResourceConfig, event.resource_config).selector
    include_active_projects = selector.include_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(include_active_projects=include_active_projects),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for pipelines")
        project_map = {
            str(project["id"]): {"path_with_namespace": project["path_with_namespace"]}
            for project in projects_batch
        }

        async for pipelines_batch in client.get_projects_resource(
            projects_batch, "pipelines"
        ):
            if pipelines_batch:
                enriched_pipelines = enrich_resources_with_project(
                    pipelines_batch, project_map
                )
                if enriched_pipelines:
                    yield enriched_pipelines


@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Limit the number of jobs that are yielded to 100.
    Results will be approximately 100 (more or less).
    """
    client = create_gitlab_client()
    selector = cast(JobResourceConfig, event.resource_config).selector
    include_active_projects = selector.include_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(include_active_projects=include_active_projects),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for jobs")
        async for jobs_batch in client.get_pipeline_jobs(projects_batch):
            yield jobs_batch


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitlabMergeRequestResourceConfig, event.resource_config).selector

    states = selector.states
    updated_after = selector.updated_after_datetime
    include_active_groups = selector.include_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_active_groups=include_active_groups)
    ):
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


@ocean.on_resync(ObjectKind.TAG)
async def on_resync_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(TagResourceConfig, event.resource_config).selector
    include_active_projects = selector.include_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(include_active_projects=include_active_projects),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for tags")

        async for tags_batch in client.get_tags(
            projects_batch, max_concurrent=DEFAULT_MAX_CONCURRENT
        ):
            yield tags_batch


@ocean.on_resync(ObjectKind.RELEASE)
async def on_resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(ReleaseResourceConfig, event.resource_config).selector
    include_active_projects = selector.include_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(include_active_projects=include_active_projects),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for releases")

        async for releases_batch in client.get_releases(
            projects_batch, max_concurrent=DEFAULT_MAX_CONCURRENT
        ):
            yield releases_batch


@ocean.on_resync(ObjectKind.GROUP_WITH_MEMBERS)
async def on_resync_groups_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(
        GitlabGroupWithMembersResourceConfig, event.resource_config
    ).selector
    include_bot_members = bool(selector.include_bot_members)
    include_inherited_members = selector.include_inherited_members
    include_active_groups = selector.include_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_active_groups=include_active_groups)
    ):
        for i in range(0, len(groups_batch), RESYNC_GROUP_MEMBERS_BATCH_SIZE):
            current_batch = groups_batch[i : i + RESYNC_GROUP_MEMBERS_BATCH_SIZE]
            logger.info(
                f"Processing members for {i + len(current_batch)}/{len(groups_batch)} groups"
            )

            tasks = [
                client.enrich_group_with_members(
                    group, include_bot_members, include_inherited_members
                )
                for group in current_batch
            ]
            results = await asyncio.gather(*tasks)
            yield results


@ocean.on_resync(ObjectKind.MEMBER)
async def on_resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitlabMemberResourceConfig, event.resource_config).selector
    include_bot_members = bool(selector.include_bot_members)
    include_inherited_members = selector.include_inherited_members
    include_active_groups = selector.include_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_active_groups=include_active_groups)
    ):
        for i in range(0, len(groups_batch), RESYNC_GROUP_MEMBERS_BATCH_SIZE):
            current_batch = groups_batch[i : i + RESYNC_GROUP_MEMBERS_BATCH_SIZE]
            tasks = [
                client.get_group_members(
                    group["id"], include_bot_members, include_inherited_members
                )
                for group in current_batch
            ]
            async for batch in stream_async_iterators_tasks(*tasks):
                if batch:
                    yield batch


@ocean.on_resync(ObjectKind.FILE)
async def on_resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(GitLabFilesResourceConfig, event.resource_config).selector
    include_active_groups = selector.include_active_groups

    search_path = selector.files.path
    scope = "blobs"
    skip_parsing = selector.files.skip_parsing

    repositories = (
        selector.files.repos
        if hasattr(selector.files, "repos") and selector.files.repos
        else None
    )

    async for files_batch in client.search_files(
        scope,
        search_path,
        repositories,
        skip_parsing,
        build_group_params(include_active_groups=include_active_groups),
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
            # If no repos specified, sync folders from all projects
            logger.info(
                f"No repositories specified for path {path}; syncing from all projects"
            )
            include_active_projects = selector.include_active_projects
            async for projects_batch in client.get_projects(
                params=build_project_params(
                    include_active_projects=include_active_projects
                ),
                max_concurrent=DEFAULT_MAX_CONCURRENT,
                include_languages=False,
            ):
                for project in projects_batch:
                    async for folders_batch in client.get_repository_folders(
                        path=path,
                        repository=project["path_with_namespace"],
                        branch=None,
                    ):
                        if folders_batch:
                            logger.info(
                                f"Found {len(folders_batch)} folders in {project['path_with_namespace']}"
                            )
                            yield folders_batch
        else:
            # Process specific repos
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
ocean.add_webhook_processor("/hook/{group_id}", ProjectWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", TagWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", ReleaseWebhookProcessor)
