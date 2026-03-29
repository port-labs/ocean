from itertools import batched
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
    GitlabProjectWithMembersResourceConfig,
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
from gitlab.webhook.webhook_processors.project_with_member_webhook_processor import (
    ProjectWithMemberWebhookProcessor,
)
from gitlab.webhook.webhook_processors.tag_webhook_processor import (
    TagWebhookProcessor,
)
from gitlab.webhook.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from gitlab.clients.options import IssueOptions

RESYNC_MEMBERS_BATCH_SIZE = 10
DEFAULT_MAX_CONCURRENT = 10


async def _fetch_included_files_content(
    client: Any,
    project: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Fetch included files for a project. Returns dict of file_path -> content."""
    project_path = project.get("path_with_namespace", str(project.get("id", "")))
    ref = project.get("default_branch", "main")
    included: dict[str, Any] = {}
    for file_path in file_paths:
        try:
            content = await client.get_file_content(project_path, file_path, ref)
            included[file_path] = content
        except Exception:
            logger.debug(
                f"Could not fetch file '{file_path}' from {project_path}@{ref}"
            )
            included[file_path] = None
    return included


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
    include_only_active_projects = selector.include_only_active_projects
    search_queries = (
        [sq.dict() for sq in selector.search_queries]
        if selector.search_queries
        else None
    )
    included_files = selector.included_files or []

    params = build_project_params(
        include_only_active_projects=include_only_active_projects
    )
    async for projects_batch in client.get_projects(
        params=params,
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=include_languages,
        search_queries=search_queries,
        included_files=included_files if included_files else None,
    ):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        yield projects_batch


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GroupResourceConfig, event.resource_config).selector
    include_only_active_groups = selector.include_only_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_only_active_groups=include_only_active_groups)
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
        params=build_group_params(
            include_only_active_groups=selector.include_only_active_groups
        )
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
    include_only_active_projects = selector.include_only_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
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
    include_only_active_projects = selector.include_only_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
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
    include_only_active_groups = selector.include_only_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_only_active_groups=include_only_active_groups)
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
    include_only_active_projects = selector.include_only_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
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
    include_only_active_projects = selector.include_only_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
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
    include_only_active_groups = selector.include_only_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_only_active_groups=include_only_active_groups)
    ):
        for i in range(0, len(groups_batch), RESYNC_MEMBERS_BATCH_SIZE):
            current_batch = groups_batch[i : i + RESYNC_MEMBERS_BATCH_SIZE]
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
    include_only_active_groups = selector.include_only_active_groups

    async for groups_batch in client.get_groups(
        params=build_group_params(include_only_active_groups=include_only_active_groups)
    ):
        for i in range(0, len(groups_batch), RESYNC_MEMBERS_BATCH_SIZE):
            current_batch = groups_batch[i : i + RESYNC_MEMBERS_BATCH_SIZE]
            tasks = [
                client.get_group_members(
                    group["id"], include_bot_members, include_inherited_members
                )
                for group in current_batch
            ]
            async for batch in stream_async_iterators_tasks(*tasks):
                if batch:
                    yield batch


@ocean.on_resync(ObjectKind.PROJECT_WITH_MEMBERS)
async def on_resync_projects_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(
        GitlabProjectWithMembersResourceConfig, event.resource_config
    ).selector
    include_bot_members = bool(selector.include_bot_members)
    include_inherited_members = selector.include_inherited_members
    include_only_active_projects = selector.include_only_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        for batch in batched(projects_batch, RESYNC_MEMBERS_BATCH_SIZE):
            logger.info(f"Processing members for batch of {len(batch)} projects")
            tasks = [
                client.enrich_project_with_members(
                    project, include_bot_members, include_inherited_members
                )
                for project in batch
            ]
            results = await asyncio.gather(*tasks)
            yield list(results)


@ocean.on_resync(ObjectKind.FILE)
async def on_resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(GitLabFilesResourceConfig, event.resource_config).selector
    include_only_active_groups = selector.include_only_active_groups
    included_files = selector.included_files or []

    search_path = selector.files.path
    scope = "blobs"
    skip_parsing = selector.files.skip_parsing

    repositories = (
        selector.files.repos
        if hasattr(selector.files, "repos") and selector.files.repos
        else None
    )

    files_cache: dict[str, dict[str, Any]] = {}
    found_any_files = False

    async def _enrich_and_yield(
        files_batch: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched_batch = await client._enrich_files_with_repos(files_batch)
        if included_files:
            for file_entity in enriched_batch:
                repo = file_entity.get("repo", {})
                repo_key = str(repo.get("id", repo.get("path_with_namespace", "")))
                if repo_key not in files_cache:
                    files_cache[repo_key] = await _fetch_included_files_content(
                        client, repo, included_files
                    )
                file_entity["__includedFiles"] = files_cache[repo_key]
        return enriched_batch

    async for files_batch in client.search_files(
        scope,
        search_path,
        repositories,
        skip_parsing,
        build_group_params(include_only_active_groups=include_only_active_groups),
    ):
        enriched_batch = await _enrich_and_yield(files_batch)
        if enriched_batch:
            found_any_files = True
            yield enriched_batch

    if not found_any_files and not repositories:
        logger.info(
            "Group-level file search returned no results. "
            "Falling back to project-level file search."
        )
        # control project filtering using group selector to avoid adding a new selector
        params = build_project_params(
            include_only_active_projects=include_only_active_groups
        )
        async for files_batch in client.search_files_in_projects(
            scope,
            search_path,
            skip_parsing,
            params,
        ):
            enriched_batch = await _enrich_and_yield(files_batch)
            if enriched_batch:
                yield enriched_batch


@ocean.on_resync(ObjectKind.FOLDER)
async def on_resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitLabFoldersResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []

    include_only_active_projects = selector.include_only_active_projects
    projects_params = build_project_params(
        include_only_active_projects=include_only_active_projects
    )
    for folder_selector in selector.folders:
        path = folder_selector.path
        repos = folder_selector.repos

        if not repos:
            # If no repos specified, sync folders from all projects
            logger.info(
                f"No repositories specified for path {path}; syncing from all projects"
            )

            async for projects_batch in client.get_projects(
                params=projects_params,
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
                            if included_files:
                                from gitlab.enrichments.included_files import (
                                    IncludedFilesEnricher,
                                    FolderIncludedFilesStrategy,
                                )

                                enricher = IncludedFilesEnricher(
                                    client=client,
                                    strategy=FolderIncludedFilesStrategy(
                                        folder_selectors=selector.folders,
                                        global_included_files=included_files,
                                    ),
                                )
                                folders_batch = await enricher.enrich_batch(
                                    folders_batch
                                )
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
                    if included_files and folders_batch:
                        from gitlab.enrichments.included_files import (
                            IncludedFilesEnricher,
                            FolderIncludedFilesStrategy,
                        )

                        enricher = IncludedFilesEnricher(
                            client=client,
                            strategy=FolderIncludedFilesStrategy(
                                folder_selectors=selector.folders,
                                global_included_files=included_files,
                            ),
                        )
                        folders_batch = await enricher.enrich_batch(folders_batch)
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
ocean.add_webhook_processor("/hook/{group_id}", ProjectWithMemberWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", TagWebhookProcessor)
ocean.add_webhook_processor("/hook/{group_id}", ReleaseWebhookProcessor)
