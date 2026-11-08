from itertools import batched
from typing import AsyncIterator, cast, Any

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from gitlab.actions.registry import register_actions_executors
from gitlab.oauth.registry import register_oauth_provider
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
)
import asyncio
from gitlab.clients.client_factory import create_gitlab_client
from gitlab.clients.utils import (
    build_group_params,
    build_issue_params,
    build_merge_request_params,
    build_pipeline_params,
    build_project_params,
    build_branch_params,
)
from gitlab.helpers.utils import (
    ObjectKind,
    build_search_query,
    enrich_resources_with_project,
)
from gitlab.helpers.incremental import (
    build_cursor_updated_after_params,
    build_incremental_merge_request_params,
    build_incremental_pipeline_params,
    build_incremental_project_updated_params,
    build_incremental_projects_params,
)
from gitlab.helpers.skill_plugin_resync import (
    resync_plugins,
    resync_plugins_incremental,
    resync_skills,
    resync_skills_incremental,
)
from integration import (
    GitLabFilesResourceConfig,
    GitLabSkillResourceConfig,
    GitLabPluginResourceConfig,
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
    BranchResourceConfig,
    GitlabDeploymentResourceConfig,
)

from gitlab.webhook.constants import WEBHOOK_PATH
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
from gitlab.webhook.webhook_factory.project_webhook_factory import ProjectWebHook
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
from gitlab.webhook.webhook_processors.skill_push_webhook_processor import (
    SkillPushWebhookProcessor,
)
from gitlab.webhook.webhook_processors.plugin_push_webhook_processor import (
    PluginPushWebhookProcessor,
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
from gitlab.webhook.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)
from gitlab.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
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
        client = create_gitlab_client()

        logger.info(f"Creating webhooks for all groups at {base_url}")
        group_webhook_factory = GroupWebHook(client, base_url)
        await group_webhook_factory.create_webhooks_for_all_groups()

        logger.info(f"Creating webhooks for personal namespace projects at {base_url}")
        project_webhook_factory = ProjectWebHook(client, base_url)
        await project_webhook_factory.create_webhooks_for_personal_projects()


@ocean.on_incremental_resync(ObjectKind.PROJECT)
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync projects; incremental only fetches projects updated since the cursor."""
    client = create_gitlab_client()
    selector = cast(ProjectResourceConfig, event.resource_config).selector
    include_languages = bool(selector.include_languages)
    include_only_active_projects = selector.include_only_active_projects
    sync_cursor = active_incremental_cursor()
    search_queries = (
        [sq.dict() for sq in selector.search_queries]
        if selector.search_queries
        else None
    )
    included_files = selector.included_files or []

    if sync_cursor is None:
        params = build_project_params(
            include_only_active_projects=include_only_active_projects
        )
    else:
        params = build_incremental_projects_params(
            include_only_active_projects, sync_cursor
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


@ocean.on_incremental_resync(ObjectKind.ISSUE)
@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync group issues; incremental runs only fetch issues updated since the cursor."""
    client = create_gitlab_client()
    selector = cast(GitlabIssueResourceConfig, event.resource_config).selector
    sync_cursor = active_incremental_cursor()
    options = IssueOptions(
        issue_type=selector.issue_type,
        labels=selector.labels,
        non_archived=selector.non_archived,
        state=selector.state,
    )
    if sync_cursor is None:
        params = build_issue_params(options, selector.updated_after_datetime)
    else:
        params = build_issue_params(options, sync_cursor)

    async for groups_batch in client.get_groups(
        params=build_group_params(
            include_only_active_groups=selector.include_only_active_groups
        )
    ):
        logger.info(f"Processing batch of {len(groups_batch)} groups for issues")
        async for issues_batch in client.get_groups_resource(
            groups_batch, "issues", params=params
        ):
            yield issues_batch


@ocean.on_incremental_resync(ObjectKind.PIPELINE)
@ocean.on_resync(ObjectKind.PIPELINE)
async def on_resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync project pipelines; incremental only fetches pipelines updated since the cursor."""
    client = create_gitlab_client()
    selector = cast(PipelineResourceConfig, event.resource_config).selector
    include_only_active_projects = selector.include_only_active_projects
    sync_cursor = active_incremental_cursor()

    api_query_params = (
        selector.api_query_params.generate_query_params()
        if selector.api_query_params
        else None
    )
    if sync_cursor is None:
        params = build_pipeline_params(api_query_params)
    else:
        params = build_incremental_pipeline_params(api_query_params, sync_cursor)

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
            projects_batch, "pipelines", params=params or None
        ):
            if pipelines_batch:
                enriched_pipelines = enrich_resources_with_project(
                    pipelines_batch, project_map
                )
                if enriched_pipelines:
                    yield enriched_pipelines


@ocean.on_incremental_resync(ObjectKind.JOB)
@ocean.on_resync(ObjectKind.JOB)
async def on_resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync pipeline jobs.

    Incremental runs only include projects updated since the cursor, then
    pipelines updated since the cursor.
    """
    client = create_gitlab_client()
    selector = cast(JobResourceConfig, event.resource_config).selector
    include_only_active_projects = selector.include_only_active_projects
    sync_cursor = active_incremental_cursor()

    pipeline_query_params = (
        selector.pipeline_query_params.generate_query_params()
        if selector.pipeline_query_params
        else None
    )
    if sync_cursor is None:
        pipeline_params = build_pipeline_params(pipeline_query_params)
        projects_params = build_project_params(
            include_only_active_projects=include_only_active_projects
        )
    else:
        pipeline_params = build_incremental_pipeline_params(
            pipeline_query_params, sync_cursor
        )
        projects_params = build_incremental_project_updated_params(
            include_only_active_projects, sync_cursor
        )

    async for projects_batch in client.get_projects(
        params=projects_params,
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for jobs")
        async for jobs_batch in client.get_pipeline_jobs(
            projects_batch, pipeline_params=pipeline_params or None
        ):
            yield jobs_batch


@ocean.on_incremental_resync(ObjectKind.MERGE_REQUEST)
@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync group MRs; incremental runs only fetch MRs updated since the cursor."""
    client = create_gitlab_client()
    selector = cast(GitlabMergeRequestResourceConfig, event.resource_config).selector

    states = selector.states
    sync_cursor = active_incremental_cursor()
    lookback_updated_after = selector.updated_after_datetime
    include_only_active_groups = selector.include_only_active_groups
    enrich_with_commits = selector.enrich_with_commits
    enrich_with_review_discussion = selector.enrich_with_review_discussion
    needs_enrichment = enrich_with_commits or enrich_with_review_discussion

    async for groups_batch in client.get_groups(
        params=build_group_params(include_only_active_groups=include_only_active_groups)
    ):
        for state in states:
            if sync_cursor is None:
                params = build_merge_request_params(state, lookback_updated_after)
            else:
                params = build_incremental_merge_request_params(state, sync_cursor)
            logger.info(
                f"Processing batch of {len(groups_batch)} groups for {state} merge requests"
            )

            async for merge_requests_batch in client.get_groups_resource(
                groups_batch, "merge_requests", params=params
            ):
                if needs_enrichment:
                    merge_requests_batch = await client.enrich_merge_requests(
                        merge_requests_batch,
                        enrich_with_commits=enrich_with_commits,
                        enrich_with_review_discussion=enrich_with_review_discussion,
                        max_concurrent=DEFAULT_MAX_CONCURRENT,
                    )
                yield merge_requests_batch


@ocean.on_incremental_resync(ObjectKind.TAG)
@ocean.on_resync(ObjectKind.TAG)
async def on_resync_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync project tags; incremental scans projects updated since the cursor."""
    client = create_gitlab_client()
    selector = cast(TagResourceConfig, event.resource_config).selector
    include_only_active_projects = selector.include_only_active_projects
    sync_cursor = active_incremental_cursor()

    if sync_cursor is None:
        projects_params = build_project_params(
            include_only_active_projects=include_only_active_projects
        )
    else:
        projects_params = build_incremental_project_updated_params(
            include_only_active_projects, sync_cursor
        )
    async for projects_batch in client.get_projects(
        params=projects_params,
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for tags")

        async for tags_batch in client.get_tags(
            projects_batch, max_concurrent=DEFAULT_MAX_CONCURRENT
        ):
            yield tags_batch


@ocean.on_incremental_resync(ObjectKind.RELEASE)
@ocean.on_resync(ObjectKind.RELEASE)
async def on_resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync project releases; incremental scans projects updated since the cursor."""
    client = create_gitlab_client()
    selector = cast(ReleaseResourceConfig, event.resource_config).selector
    include_only_active_projects = selector.include_only_active_projects
    sync_cursor = active_incremental_cursor()

    if sync_cursor is None:
        projects_params = build_project_params(
            include_only_active_projects=include_only_active_projects
        )
    else:
        projects_params = build_incremental_project_updated_params(
            include_only_active_projects, sync_cursor
        )
    async for projects_batch in client.get_projects(
        params=projects_params,
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for releases")

        async for releases_batch in client.get_releases(
            projects_batch, max_concurrent=DEFAULT_MAX_CONCURRENT
        ):
            yield releases_batch


@ocean.on_resync(ObjectKind.BRANCH)
async def on_resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(BranchResourceConfig, event.resource_config).selector
    include_only_active_projects = selector.include_only_active_projects

    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(f"Processing batch of {len(projects_batch)} projects for branches")

        async for branches_batch in client.get_branches(
            projects_batch,
            max_concurrent=DEFAULT_MAX_CONCURRENT,
            default_branches_only=selector.default_branch_only,
            params=(
                build_branch_params(selector)
                if not selector.default_branch_only
                else None
            ),
        ):
            yield branches_batch


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
        for batch in batched(groups_batch, RESYNC_MEMBERS_BATCH_SIZE):
            logger.info(f"Processing members for batch of {len(batch)} groups")
            tasks = [
                client.enrich_group_with_members(
                    group, include_bot_members, include_inherited_members
                )
                for group in batch
            ]
            results = await asyncio.gather(*tasks)
            yield list(results)


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
        for batch in batched(groups_batch, RESYNC_MEMBERS_BATCH_SIZE):
            tasks = [
                client.get_group_members(
                    group["id"], include_bot_members, include_inherited_members
                )
                for group in batch
            ]
            async for members_batch in stream_async_iterators_tasks(*tasks):
                if members_batch:
                    yield members_batch


@ocean.on_resync(ObjectKind.PROJECT_WITH_MEMBERS)
async def on_resync_projects_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Full resync only — membership changes do not reliably bump last_activity_at."""
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


@ocean.on_incremental_resync(ObjectKind.FILE)
@ocean.on_resync(ObjectKind.FILE)
async def on_resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(GitLabFilesResourceConfig, event.resource_config).selector
    include_only_active_groups = selector.include_only_active_groups
    included_files = selector.included_files or []

    search_path = selector.files.path
    scope = "blobs"
    skip_parsing = selector.files.skip_parsing
    search_strategy = selector.files.search_strategy
    sync_cursor = active_incremental_cursor()

    repositories = (
        selector.files.repos
        if hasattr(selector.files, "repos") and selector.files.repos
        else None
    )

    files_cache: dict[str, dict[str, Any]] = {}

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

    lists_projects = search_strategy in ("projectSearch", "repositoryTree")
    if not lists_projects:
        # groupSearch lists groups, which aren't filtered by the cursor,
        # so full and incremental runs send the same query.
        params = build_group_params(
            include_only_active_groups=include_only_active_groups
        )
    elif sync_cursor is None:
        params = build_project_params(
            include_only_active_projects=include_only_active_groups
        )
    else:
        params = build_incremental_project_updated_params(
            include_only_active_groups, sync_cursor
        )

    if sync_cursor is not None and search_strategy == "repositoryTree":
        files_stream = client.search_changed_files_in_projects(
            build_search_query(search_path),
            sync_cursor,
            skip_parsing=skip_parsing,
            repositories=repositories,
            params=params,
        )
    else:
        files_stream = client.search_files(
            scope,
            build_search_query(search_path),
            skip_parsing=skip_parsing,
            repositories=repositories,
            params=params,
            strategy=search_strategy,
        )

    async for files_batch in files_stream:
        enriched_batch = await _enrich_and_yield(files_batch)
        if enriched_batch:
            yield enriched_batch


@ocean.on_incremental_resync(ObjectKind.SKILL)
@ocean.on_resync(ObjectKind.SKILL)
async def on_resync_skills(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitLabSkillResourceConfig, event.resource_config).selector
    sync_cursor = active_incremental_cursor()
    if sync_cursor is None:
        project_params = build_project_params(
            include_only_active_projects=selector.include_only_active_groups
        )
        stream = resync_skills(client, selector, project_params)
    else:
        project_params = build_incremental_project_updated_params(
            selector.include_only_active_groups, sync_cursor
        )
        stream = resync_skills_incremental(
            client, selector, project_params, sync_cursor
        )
    async for batch in stream:
        yield batch


@ocean.on_incremental_resync(ObjectKind.PLUGIN)
@ocean.on_resync(ObjectKind.PLUGIN)
async def on_resync_plugins(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitLabPluginResourceConfig, event.resource_config).selector
    sync_cursor = active_incremental_cursor()
    if sync_cursor is None:
        project_params = build_project_params(
            include_only_active_projects=selector.include_only_active_groups
        )
        stream = resync_plugins(client, selector, project_params)
    else:
        project_params = build_incremental_project_updated_params(
            selector.include_only_active_groups, sync_cursor
        )
        stream = resync_plugins_incremental(
            client, selector, project_params, sync_cursor
        )
    async for batch in stream:
        yield batch


@ocean.on_incremental_resync(ObjectKind.FOLDER)
@ocean.on_resync(ObjectKind.FOLDER)
async def on_resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitLabFoldersResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []

    include_only_active_projects = selector.include_only_active_projects
    sync_cursor = active_incremental_cursor()
    if sync_cursor is None:
        projects_params = build_project_params(
            include_only_active_projects=include_only_active_projects
        )
    else:
        projects_params = build_incremental_project_updated_params(
            include_only_active_projects, sync_cursor
        )

    def folders_stream(
        path: str, repository: str, branch: str | None = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if sync_cursor is not None:
            return client.get_repository_folders_since(
                path, repository, sync_cursor, branch
            )
        return client.get_repository_folders(
            path=path, repository=repository, branch=branch
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
                    async for folders_batch in folders_stream(
                        path, project["path_with_namespace"]
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
                async for folders_batch in folders_stream(path, repo.name, repo.branch):
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


async def _resync_deployments(
    include_only_active_projects: bool | None,
    params: dict[str, Any] | None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    async for projects_batch in client.get_projects(
        params=build_project_params(
            include_only_active_projects=include_only_active_projects
        ),
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        include_languages=False,
    ):
        logger.info(
            f"Processing batch of {len(projects_batch)} projects for deployments"
        )
        async for deployments_batch in client.get_deployments(
            projects_batch,
            max_concurrent=DEFAULT_MAX_CONCURRENT,
            params=params,
        ):
            yield deployments_batch


@ocean.on_incremental_resync(ObjectKind.DEPLOYMENT)
@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def on_resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync project deployments; incremental only fetches those updated since the cursor."""
    selector = cast(GitlabDeploymentResourceConfig, event.resource_config).selector
    sync_cursor = active_incremental_cursor()
    selector_params = selector.generate_query_params() or None
    if sync_cursor is None:
        params = selector_params
    else:
        params = build_cursor_updated_after_params(selector_params, sync_cursor)
    async for batch in _resync_deployments(
        selector.include_only_active_projects,
        params,
    ):
        yield batch


ocean.add_webhook_processor(WEBHOOK_PATH, GroupWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, MergeRequestWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, IssueWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, PushWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, PipelineWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, JobWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, MemberWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, GroupWithMemberWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, FilePushWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, SkillPushWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, PluginPushWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, FolderPushWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, ProjectWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, ProjectWithMemberWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, TagWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, ReleaseWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, BranchWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, DeploymentWebhookProcessor)

register_actions_executors()
register_oauth_provider()
