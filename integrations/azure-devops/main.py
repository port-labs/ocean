import asyncio
from typing import Any, cast

from loguru import logger

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.misc import (
    create_closed_pull_request_search_criteria,
    ACTIVE_PULL_REQUEST_SEARCH_CRITERIA,
    Kind,
    AzureDevopsFolderResourceConfig,
)
from azure_devops.webhooks.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.gitops_webhook_processor import (
    GitopsWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pull_request_processor import (
    PullRequestWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.repository_processor import (
    RepositoryWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.work_item_webhook_processor import (
    WorkItemWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.advanced_security_webhook_processor import (
    AdvancedSecurityWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor import (
    PipelineStageWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor import (
    PipelineRunWebhookProcessor,
)
from integration import (
    AzureDevopsPipelineResourceConfig,
    AzureDevopsProjectResourceConfig,
    AzureDevopsFileResourceConfig,
    AzureDevopsTeamResourceConfig,
    AzureDevopsWorkItemResourceConfig,
    AzureDevopsTestRunResourceConfig,
    AzureDevopsPullRequestResourceConfig,
    AzureDevopsAdvancedSecurityResourceConfig,
    AzureDevopsGroupMemberResourceConfig,
    AzureDevopsRepositoryResourceConfig,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


@ocean.on_resync(Kind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()

    selector = cast(AzureDevopsProjectResourceConfig, event.resource_config).selector
    sync_default_team = selector.default_team

    async for projects in azure_devops_client.generate_projects(sync_default_team):
        logger.info(f"Resyncing {len(projects)} projects")
        yield projects


@ocean.on_resync(Kind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for users in azure_devops_client.generate_users():
        logger.info(f"Resyncing {len(users)} members")
        yield users


@ocean.on_resync(Kind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(AzureDevopsTeamResourceConfig, event.resource_config).selector

    async for teams in azure_devops_client.generate_teams():
        logger.info(f"Resyncing {len(teams)} teams")
        if selector.include_members:
            logger.info(f"Enriching {len(teams)} teams with members")
            team_with_members = await azure_devops_client.enrich_teams_with_members(
                teams
            )
            yield team_with_members
        else:
            yield teams


@ocean.on_resync(Kind.MEMBER)
async def resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for members in azure_devops_client.generate_members():
        logger.info(f"Resyncing {len(members)} members")
        yield members


@ocean.on_resync(Kind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for groups in azure_devops_client.generate_groups():
        logger.info(f"Resyncing {len(groups)} groups")
        yield groups


@ocean.on_resync(Kind.GROUP_MEMBER)
async def resync_group_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(
        AzureDevopsGroupMemberResourceConfig, event.resource_config
    ).selector
    async for members in azure_devops_client.generate_group_members(
        max_depth=selector.depth
    ):
        logger.info(f"Resyncing {len(members)} group members")
        yield members


@ocean.on_resync(Kind.PIPELINE)
async def resync_pipeline(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    config = cast(AzureDevopsPipelineResourceConfig, event.resource_config)
    include_repo = config.selector.include_repo

    async for pipelines in azure_devops_client.generate_pipelines():
        logger.info(f"Resyncing {len(pipelines)} pipelines")
        if include_repo:
            logger.info(f"Enriching {len(pipelines)} pipelines with repository")
            pipelines = await azure_devops_client.enrich_pipelines_with_repository(
                pipelines
            )
        yield pipelines


@ocean.on_resync(Kind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(
        AzureDevopsPullRequestResourceConfig, event.resource_config
    ).selector

    async for pull_requests in azure_devops_client.generate_pull_requests(
        ACTIVE_PULL_REQUEST_SEARCH_CRITERIA
    ):
        logger.info(f"Resyncing {len(pull_requests)} active pull_requests")
        yield pull_requests

    for search_filter in create_closed_pull_request_search_criteria(
        selector.min_time_datetime
    ):
        async for pull_requests in azure_devops_client.generate_pull_requests(
            search_filter, selector.max_results
        ):
            logger.info(
                f"Resyncing {len(pull_requests)} abandoned/completed pull_requests"
            )
            yield pull_requests


async def _enrich_repo_with_included_files(
    client: AzureDevopsClient,
    repo: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a repository dict with __includedFiles from the given file paths."""
    repo_id = repo.get("id", "")
    default_branch_ref = repo.get("defaultBranch", "refs/heads/main")
    # Strip the refs/heads/ prefix to get the branch name
    branch_name = default_branch_ref.replace("refs/heads/", "")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content_bytes = await client.get_file_by_branch(
                file_path, repo_id, branch_name
            )
            included[file_path] = (
                content_bytes.decode("utf-8") if content_bytes else None
            )
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from repo {repo.get('name', repo_id)}@{branch_name}: {e}"
            )
            included[file_path] = None

    repo["__includedFiles"] = included
    return repo


async def _enrich_repos_batch_with_included_files(
    client: AzureDevopsClient,
    repositories: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of repositories with included files."""
    tasks = [
        _enrich_repo_with_included_files(client, repo, file_paths)
        for repo in repositories
    ]
    return list(await asyncio.gather(*tasks))


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(AzureDevopsRepositoryResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []

    async for repositories in azure_devops_client.generate_repositories():
        logger.info(f"Resyncing {len(repositories)} repositories")
        if included_files:
            repositories = await _enrich_repos_batch_with_included_files(
                azure_devops_client, repositories, included_files
            )
        yield repositories


@ocean.on_resync(Kind.BRANCH)
async def resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()

    async for branches in azure_devops_client.generate_branches():
        logger.info(f"Resyncing {len(branches)} branches")
        yield branches


@ocean.on_resync(Kind.REPOSITORY_POLICY)
async def resync_repository_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for policies in azure_devops_client.generate_repository_policies():
        logger.info(f"Resyncing {len(policies)} repository policies")
        yield policies


@ocean.on_resync(Kind.WORK_ITEM)
async def resync_workitems(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    config = cast(AzureDevopsWorkItemResourceConfig, event.resource_config)
    async for work_items in azure_devops_client.generate_work_items(
        wiql=config.selector.wiql, expand=config.selector.expand
    ):
        logger.info(f"Resyncing {len(work_items)} work items")
        yield work_items


@ocean.on_resync(Kind.COLUMN)
async def resync_columns(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for columns in azure_devops_client.get_columns():
        logger.info(f"Resyncing {len(columns)} columns")
        yield columns


@ocean.on_resync(Kind.BOARD)
async def resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for boards in azure_devops_client.get_boards_in_organization():
        logger.info(f"Resyncing {len(boards)} boards")
        yield boards


@ocean.on_resync(Kind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for releases in azure_devops_client.generate_releases():
        logger.info(f"Resyncing {len(releases)} releases")
        yield releases


@ocean.on_resync(Kind.BUILD)
async def resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for builds in azure_devops_client.generate_builds():
        logger.info(f"Resyncing {len(builds)} builds")
        yield builds


@ocean.on_resync(Kind.PIPELINE_STAGE)
async def resync_pipeline_stages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for stages in azure_devops_client.generate_pipeline_stages():
        logger.info(f"Resyncing {len(stages)} pipeline stages")
        yield stages


@ocean.on_resync(Kind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for environments in azure_devops_client.generate_environments():
        logger.info(f"Fetched {len(environments)} environments")
        yield environments


@ocean.on_resync(Kind.RELEASE_DEPLOYMENT)
async def resync_release_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()

    async for deployments in azure_devops_client.generate_release_deployments():
        logger.info(f"Fetched {len(deployments)} release deployments")
        yield deployments


@ocean.on_resync(Kind.PIPELINE_DEPLOYMENT)
async def resync_pipeline_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()

    async for environments in azure_devops_client.generate_environments():
        tasks = [
            azure_devops_client.generate_pipeline_deployments(
                environment_id=environment["id"],
                project=environment["project"],
            )
            for environment in environments
        ]
        async for deployments in stream_async_iterators_tasks(*tasks):
            logger.info(f"Fetched {len(deployments)} pipeline deployments")
            yield deployments


async def _enrich_folder_with_included_files(
    client: AzureDevopsClient,
    folder: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a folder entity with __includedFiles from the given file paths."""
    repo = folder.get("__repository", {})
    repo_id = repo.get("id", "")
    branch = folder.get("__branch") or repo.get(
        "defaultBranch", "refs/heads/main"
    ).replace("refs/heads/", "")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content_bytes = await client.get_file_by_branch(file_path, repo_id, branch)
            included[file_path] = (
                content_bytes.decode("utf-8") if content_bytes else None
            )
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from repo {repo.get('name', repo_id)}@{branch}: {e}"
            )
            included[file_path] = None

    folder["__includedFiles"] = included
    return folder


async def _enrich_folders_batch_with_included_files(
    client: AzureDevopsClient,
    folders: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of folders with included files."""
    tasks = [
        _enrich_folder_with_included_files(client, folder, file_paths)
        for folder in folders
    ]
    return list(await asyncio.gather(*tasks))


async def _enrich_file_entity_with_included_files(
    client: AzureDevopsClient,
    file_entity: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a file entity with __includedFiles from the given file paths."""
    repo = file_entity.get("repo", {})
    repo_id = repo.get("id", "")
    branch = repo.get("defaultBranch", "refs/heads/main").replace("refs/heads/", "")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content_bytes = await client.get_file_by_branch(file_path, repo_id, branch)
            included[file_path] = (
                content_bytes.decode("utf-8") if content_bytes else None
            )
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from repo {repo.get('name', repo_id)}@{branch}: {e}"
            )
            included[file_path] = None

    file_entity["__includedFiles"] = included
    return file_entity


async def _enrich_file_entities_batch_with_included_files(
    client: AzureDevopsClient,
    file_entities: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of file entities with included files."""
    tasks = [
        _enrich_file_entity_with_included_files(client, fe, file_paths)
        for fe in file_entities
    ]
    return list(await asyncio.gather(*tasks))


@ocean.on_resync(Kind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    config = cast(AzureDevopsFileResourceConfig, event.resource_config)
    included_files = config.selector.included_files or []

    logger.info(f"Starting file resync for paths: {config.selector.files.path}")

    async for files_batch in azure_devops_client.generate_files(
        path=config.selector.files.path,
        repos=config.selector.files.repos,
    ):
        if files_batch:
            logger.info(f"Resyncing batch of {len(files_batch)} files")
            if included_files:
                files_batch = await _enrich_file_entities_batch_with_included_files(
                    azure_devops_client, files_batch, included_files
                )
            yield files_batch


@ocean.on_resync(Kind.PIPELINE_RUN)
async def resync_pipeline_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for runs in azure_devops_client.generate_pipeline_runs():
        logger.info(f"Resyncing {len(runs)} pipeline runs")
        yield runs


@ocean.on_start()
async def setup_webhooks() -> None:
    base_url = ocean.app.base_url
    webhook_secret = ocean.integration_config.get("webhook_secret")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation for ONCE listener")
        return

    if not base_url:
        logger.warning("No base url provided, skipping webhook creation")
        return

    client = AzureDevopsClient.create_from_ocean_config()
    if ocean.integration_config.get("is_projects_limited"):
        async for projects in client.generate_projects():
            for project in projects:
                logger.info(f"Setting up webhooks for project {project['name']}")
                await client.create_webhook_subscriptions(
                    base_url, project["id"], webhook_secret
                )
    else:
        await client.create_webhook_subscriptions(
            base_url, webhook_secret=webhook_secret
        )


@ocean.on_resync(Kind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(AzureDevopsFolderResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []
    async for matching_folders in azure_devops_client.process_folder_patterns(
        selector.folders, selector.project_name
    ):
        if included_files:
            matching_folders = await _enrich_folders_batch_with_included_files(
                azure_devops_client, matching_folders, included_files
            )
        yield matching_folders


@ocean.on_resync(Kind.TEST_RUN)
async def resync_test_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(AzureDevopsTestRunResourceConfig, event.resource_config).selector
    include_results = selector.include_results
    coverage_config = selector.code_coverage

    async for test_runs in azure_devops_client.fetch_test_runs(
        include_results, coverage_config
    ):
        logger.info(f"Fetched {len(test_runs)} test runs")
        yield test_runs


@ocean.on_resync(Kind.ITERATION)
async def resync_iterations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for iterations in azure_devops_client.generate_iterations():
        logger.info(f"Resyncing {len(iterations)} iterations")
        yield iterations


@ocean.on_resync(Kind.ADVANCED_SECURITY_ALERT)
async def resync_advanced_security_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    selector = cast(
        AzureDevopsAdvancedSecurityResourceConfig, event.resource_config
    ).selector
    params: dict[str, Any] = {}
    if selector.criteria:
        params = selector.criteria.as_params

    async for repositories in azure_devops_client.generate_repositories():
        for repository in repositories:
            async for (
                security_alerts
            ) in azure_devops_client.generate_advanced_security_alerts(
                repository, params
            ):
                logger.info(f"Resyncing {len(security_alerts)} security alerts")
                yield security_alerts


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", FileWebhookProcessor)
ocean.add_webhook_processor("/webhook", GitopsWebhookProcessor)
ocean.add_webhook_processor("/webhook", FolderWebhookProcessor)
ocean.add_webhook_processor("/webhook", BranchWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkItemWebhookProcessor)
ocean.add_webhook_processor("/webhook", AdvancedSecurityWebhookProcessor)
ocean.add_webhook_processor("/webhook", PipelineWebhookProcessor)
ocean.add_webhook_processor("/webhook", PipelineStageWebhookProcessor)
ocean.add_webhook_processor("/webhook", PipelineRunWebhookProcessor)
