from typing import Any, AsyncGenerator, cast

from loguru import logger

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.enrichments.included_files import (
    FileIncludedFilesStrategy,
    FolderIncludedFilesStrategy,
    IncludedFilesEnricher,
    RepositoryIncludedFilesStrategy,
)
from azure_devops.helpers import resync
from azure_devops.helpers.multi_org import iterate_per_organization
from azure_devops.misc import (
    ACTIVE_PULL_REQUEST_SEARCH_CRITERIA,
    ORG_URL_FIELD,
    AzureDevopsFolderResourceConfig,
    Kind,
    create_closed_pull_request_search_criteria,
)
from azure_devops.webhooks.setup import setup_webhooks_for_all_orgs
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
from azure_devops.webhooks.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.release_definition_webhook_processor import (
    ReleaseDefinitionWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.test_run_webhook_processor import (
    TestRunWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor import (
    ReleaseDeploymentWebhookProcessor,
)
from integration import (
    AzureDevopsPipelineResourceConfig,
    AzureDevopsProjectResourceConfig,
    AzureDevopsFileResourceConfig,
    AzureDevopsReleaseConfig,
    AzureDevopsReleaseDefinitionConfig,
    AzureDevopsTeamResourceConfig,
    AzureDevopsWorkItemResourceConfig,
    AzureDevopsTestRunResourceConfig,
    AzureDevopsPullRequestResourceConfig,
    AzureDevopsAdvancedSecurityResourceConfig,
    AzureDevopsRepositoryResourceConfig,
    AzureDevopsUserConfig,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync(Kind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsProjectResourceConfig, event.resource_config).selector
    async for projects in resync.iter_projects(
        selector.default_team, selector.exclude_tag_filter
    ):
        logger.info(f"Resyncing {len(projects)} projects")
        yield projects


@ocean.on_resync(Kind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsUserConfig, event.resource_config)
    async for users in resync.iter_users(additional_params=config.selector.to_params()):
        logger.info(f"Resyncing {len(users)} members")
        yield users


@ocean.on_resync(Kind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsTeamResourceConfig, event.resource_config).selector
    async for teams in resync.iter_teams():
        logger.info(f"Resyncing {len(teams)} teams")
        if not selector.include_members:
            yield teams
            continue
        org_url = teams[0].get(ORG_URL_FIELD) if teams else None
        if not org_url:
            logger.warning("Skipping member enrichment: no org URL in teams batch")
            yield teams
            continue
        client = AzureDevopsClientManager.create_from_ocean_config().get_client_for_org(
            org_url
        )
        if not client:
            logger.warning(
                f"Skipping member enrichment: no client found for org '{org_url}'"
            )
            yield teams
            continue
        logger.info(f"Enriching {len(teams)} teams with members")
        yield await client.enrich_teams_with_members(teams)


@ocean.on_resync(Kind.MEMBER)
async def resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for members in resync.iter_members():
        logger.info(f"Resyncing {len(members)} members")
        yield members


@ocean.on_resync(Kind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for groups in resync.iter_groups():
        logger.info(f"Resyncing {len(groups)} groups")
        yield groups


@ocean.on_resync(Kind.GROUP_MEMBER)
async def resync_group_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for members in resync.iter_group_members():
        logger.info(f"Resyncing {len(members)} group members")
        yield members


@ocean.on_resync(Kind.PIPELINE)
async def resync_pipeline(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsPipelineResourceConfig, event.resource_config)
    include_repo = config.selector.include_repo
    async for pipelines in resync.iter_pipelines():
        logger.info(f"Resyncing {len(pipelines)} pipelines")
        if not include_repo:
            yield pipelines
            continue
        org_url = pipelines[0].get(ORG_URL_FIELD) if pipelines else None
        if not org_url:
            logger.warning("Skipping repo enrichment: no org URL in pipelines batch")
            yield pipelines
            continue
        client = AzureDevopsClientManager.create_from_ocean_config().get_client_for_org(
            org_url
        )
        if not client:
            logger.warning(
                f"Skipping repo enrichment: no client found for org '{org_url}'"
            )
            yield pipelines
            continue
        logger.info(f"Enriching {len(pipelines)} pipelines with repository")
        pipelines = await client.enrich_pipelines_with_repository(pipelines)
        yield pipelines


@ocean.on_resync(Kind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(
        AzureDevopsPullRequestResourceConfig, event.resource_config
    ).selector

    async for pull_requests in resync.iter_pull_requests(
        ACTIVE_PULL_REQUEST_SEARCH_CRITERIA
    ):
        logger.info(f"Resyncing {len(pull_requests)} active pull_requests")
        yield pull_requests

    for search_filter in create_closed_pull_request_search_criteria(
        selector.min_time_datetime
    ):
        async for pull_requests in resync.iter_pull_requests(
            search_filter, selector.max_results
        ):
            logger.info(
                f"Resyncing {len(pull_requests)} abandoned/completed pull_requests"
            )
            yield pull_requests


async def _enrich_repos_batch_with_included_files(
    client: AzureDevopsClient,
    repositories: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of repositories with included files."""
    if not file_paths or not repositories:
        return repositories
    enricher = IncludedFilesEnricher(
        client=client,
        strategy=RepositoryIncludedFilesStrategy(included_files=file_paths),
    )
    return await enricher.enrich_batch(repositories)


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsRepositoryResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []

    async for repositories in resync.iter_repositories():
        logger.info(f"Resyncing {len(repositories)} repositories")
        if not included_files:
            yield repositories
            continue
        org_url = repositories[0].get(ORG_URL_FIELD) if repositories else None
        if not org_url:
            logger.warning("Skipping file enrichment: no org URL in repositories batch")
            yield repositories
            continue
        client = AzureDevopsClientManager.create_from_ocean_config().get_client_for_org(
            org_url
        )
        if not client:
            logger.warning(
                f"Skipping file enrichment: no client found for org '{org_url}'"
            )
            yield repositories
            continue
        repositories = await _enrich_repos_batch_with_included_files(
            client, repositories, included_files
        )
        yield repositories


@ocean.on_resync(Kind.BRANCH)
async def resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for branches in resync.iter_branches():
        logger.info(f"Resyncing {len(branches)} branches")
        yield branches


@ocean.on_resync(Kind.REPOSITORY_POLICY)
async def resync_repository_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for policies in resync.iter_repository_policies():
        logger.info(f"Resyncing {len(policies)} repository policies")
        yield policies


@ocean.on_resync(Kind.WORK_ITEM)
async def resync_workitems(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsWorkItemResourceConfig, event.resource_config)
    async for work_items in resync.iter_work_items(
        wiql=config.selector.wiql,
        expand=config.selector.expand,
        exclude_tag_filter=config.selector.exclude_tag_filter,
    ):
        logger.info(f"Resyncing {len(work_items)} work items")
        yield work_items


@ocean.on_resync(Kind.COLUMN)
async def resync_columns(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for columns in resync.iter_columns():
        logger.info(f"Resyncing {len(columns)} columns")
        yield columns


@ocean.on_resync(Kind.BOARD)
async def resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for boards in resync.iter_boards():
        logger.info(f"Resyncing {len(boards)} boards")
        yield boards


@ocean.on_resync(Kind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsReleaseConfig, event.resource_config)
    async for releases in resync.iter_releases(
        additional_params=config.selector.to_params()
    ):
        logger.info(f"Resyncing {len(releases)} releases")
        yield releases


@ocean.on_resync(Kind.RELEASE_DEFINITION)
async def resync_release_definitions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsReleaseDefinitionConfig, event.resource_config)
    async for definitions in resync.iter_release_definitions(
        additional_params=config.selector.to_params()
    ):
        logger.info(f"Resyncing {len(definitions)} release definitions")
        yield definitions


@ocean.on_resync(Kind.BUILD)
async def resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for builds in resync.iter_builds():
        logger.info(f"Resyncing {len(builds)} builds")
        yield builds


@ocean.on_resync(Kind.PIPELINE_STAGE)
async def resync_pipeline_stages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for stages in resync.iter_pipeline_stages():
        logger.info(f"Resyncing {len(stages)} pipeline stages")
        yield stages


@ocean.on_resync(Kind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for environments in resync.iter_environments():
        logger.info(f"Fetched {len(environments)} environments")
        yield environments


@ocean.on_resync(Kind.RELEASE_DEPLOYMENT)
async def resync_release_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for deployments in resync.iter_release_deployments():
        logger.info(f"Fetched {len(deployments)} release deployments")
        yield deployments


@ocean.on_resync(Kind.PIPELINE_DEPLOYMENT)
async def resync_pipeline_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for deployments in resync.iter_pipeline_deployments():
        logger.info(f"Fetched {len(deployments)} pipeline deployments")
        yield deployments


@ocean.on_resync(Kind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsFileResourceConfig, event.resource_config)
    included_files = config.selector.included_files or []

    logger.info(f"Starting file resync for paths: {config.selector.files.path}")

    async def _handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for files_batch in client.generate_files(
            path=config.selector.files.path,
            repos=config.selector.files.repos,
        ):
            if files_batch:
                if included_files:
                    enricher = IncludedFilesEnricher(
                        client=client,
                        strategy=FileIncludedFilesStrategy(
                            included_files=included_files
                        ),
                    )
                    files_batch = await enricher.enrich_batch(files_batch)
                yield files_batch

    async for files_batch in iterate_per_organization(_handler):
        logger.info(f"Resyncing batch of {len(files_batch)} files")
        yield files_batch


@ocean.on_resync(Kind.PIPELINE_RUN)
async def resync_pipeline_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for runs in resync.iter_pipeline_runs():
        logger.info(f"Resyncing {len(runs)} pipeline runs")
        yield runs


@ocean.on_start()
async def setup_webhooks() -> None:
    await setup_webhooks_for_all_orgs()


@ocean.on_resync(Kind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    selector = cast(AzureDevopsFolderResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []

    async def _handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for matching_folders in client.process_folder_patterns(
            selector.folders, selector.project_name
        ):
            if included_files:
                enricher = IncludedFilesEnricher(
                    client=client,
                    strategy=FolderIncludedFilesStrategy(
                        folder_selectors=selector.folders,
                        global_included_files=included_files,
                    ),
                )
                matching_folders = await enricher.enrich_batch(matching_folders)
            yield matching_folders

    async for batch in iterate_per_organization(_handler):
        yield batch


@ocean.on_resync(Kind.TEST_RUN)
async def resync_test_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsTestRunResourceConfig, event.resource_config).selector
    async for test_runs in resync.iter_test_runs(
        selector.include_results, selector.code_coverage
    ):
        logger.info(f"Fetched {len(test_runs)} test runs")
        yield test_runs


@ocean.on_resync(Kind.ITERATION)
async def resync_iterations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for iterations in resync.iter_iterations():
        logger.info(f"Resyncing {len(iterations)} iterations")
        yield iterations


@ocean.on_resync(Kind.ADVANCED_SECURITY_ALERT)
async def resync_advanced_security_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(
        AzureDevopsAdvancedSecurityResourceConfig, event.resource_config
    ).selector
    params: dict[str, Any] = {}
    if selector.criteria:
        params = selector.criteria.as_params

    async for security_alerts in resync.iter_advanced_security_alerts(params):
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
ocean.add_webhook_processor("/webhook", ReleaseWebhookProcessor)
ocean.add_webhook_processor("/webhook", ReleaseDefinitionWebhookProcessor)
ocean.add_webhook_processor("/webhook", ReleaseDeploymentWebhookProcessor)
ocean.add_webhook_processor("/webhook", TestRunWebhookProcessor)
