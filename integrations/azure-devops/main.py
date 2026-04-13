from typing import Any, cast

from loguru import logger

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.enrichments.included_files import (
    FileIncludedFilesStrategy,
    FolderIncludedFilesStrategy,
    IncludedFilesEnricher,
    RepositoryIncludedFilesStrategy,
)
from azure_devops.helpers.validate_config import validate_azure_devops_config
from azure_devops.misc import (
    AzureDevopsFolderResourceConfig,
    ACTIVE_PULL_REQUEST_SEARCH_CRITERIA,
    Kind,
    create_closed_pull_request_search_criteria,
)
from azure_devops.webhooks.setup import setup_webhooks_for_all_orgs
from azure_devops.webhooks.webhook_processors.advanced_security_webhook_processor import (
    AdvancedSecurityWebhookProcessor,
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
from azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor import (
    PipelineRunWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor import (
    PipelineStageWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
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
from integration import (
    AzureDevopsAdvancedSecurityResourceConfig,
    AzureDevopsFileResourceConfig,
    AzureDevopsPipelineResourceConfig,
    AzureDevopsProjectResourceConfig,
    AzureDevopsPullRequestResourceConfig,
    AzureDevopsRepositoryResourceConfig,
    AzureDevopsTeamResourceConfig,
    AzureDevopsTestRunResourceConfig,
    AzureDevopsWorkItemResourceConfig,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


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


@ocean.on_start()
async def validate_integration_config() -> None:
    """Validate config for single or multi org setup."""
    validate_azure_devops_config(
        organization_url=ocean.integration_config.get("organization_url"),
        personal_access_token=ocean.integration_config.get("personal_access_token"),
        organization_token_mapping=ocean.integration_config.get(
            "organization_token_mapping"
        ),
    )


@ocean.on_start()
async def setup_webhooks() -> None:
    await setup_webhooks_for_all_orgs()


@ocean.on_resync(Kind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsProjectResourceConfig, event.resource_config).selector
    sync_default_team = selector.default_team

    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for projects in client.generate_projects(sync_default_team):
            logger.info(f"Resyncing {len(projects)} projects")
            yield projects


@ocean.on_resync(Kind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for users in client.generate_users():
            logger.info(f"Resyncing {len(users)} users")
            yield users


@ocean.on_resync(Kind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsTeamResourceConfig, event.resource_config).selector
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for teams in client.generate_teams():
            logger.info(f"Resyncing {len(teams)} teams")
            if selector.include_members:
                logger.info(f"Enriching {len(teams)} teams with members")
                yield await client.enrich_teams_with_members(teams)
            else:
                yield teams


@ocean.on_resync(Kind.MEMBER)
async def resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for members in client.generate_members():
            logger.info(f"Resyncing {len(members)} members")
            yield members


@ocean.on_resync(Kind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for groups in client.generate_groups():
            logger.info(f"Resyncing {len(groups)} groups")
            yield groups


@ocean.on_resync(Kind.GROUP_MEMBER)
async def resync_group_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for members in client.generate_group_members():
            logger.info(f"Resyncing {len(members)} group members")
            yield members


@ocean.on_resync(Kind.PIPELINE)
async def resync_pipeline(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsPipelineResourceConfig, event.resource_config)
    include_repo = config.selector.include_repo
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for pipelines in client.generate_pipelines():
            logger.info(f"Resyncing {len(pipelines)} pipelines")
            if include_repo:
                logger.info(f"Enriching {len(pipelines)} pipelines with repository")
                pipelines = await client.enrich_pipelines_with_repository(pipelines)
            yield pipelines


@ocean.on_resync(Kind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(
        AzureDevopsPullRequestResourceConfig, event.resource_config
    ).selector
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for pull_requests in client.generate_pull_requests(
            ACTIVE_PULL_REQUEST_SEARCH_CRITERIA
        ):
            logger.info(f"Resyncing {len(pull_requests)} active pull_requests")
            yield pull_requests

        for search_filter in create_closed_pull_request_search_criteria(
            selector.min_time_datetime
        ):
            async for pull_requests in client.generate_pull_requests(
                search_filter, selector.max_results
            ):
                logger.info(
                    f"Resyncing {len(pull_requests)} abandoned/completed pull_requests"
                )
                yield pull_requests


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsRepositoryResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for repositories in client.generate_repositories():
            logger.info(f"Resyncing {len(repositories)} repositories")
            if included_files:
                repositories = await _enrich_repos_batch_with_included_files(
                    client, repositories, included_files
                )
            yield repositories


@ocean.on_resync(Kind.BRANCH)
async def resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for branches in client.generate_branches():
            logger.info(f"Resyncing {len(branches)} branches")
            yield branches


@ocean.on_resync(Kind.REPOSITORY_POLICY)
async def resync_repository_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for policies in client.generate_repository_policies():
            logger.info(f"Resyncing {len(policies)} repository policies")
            yield policies


@ocean.on_resync(Kind.WORK_ITEM)
async def resync_workitems(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsWorkItemResourceConfig, event.resource_config)
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for work_items in client.generate_work_items(
            wiql=config.selector.wiql, expand=config.selector.expand
        ):
            logger.info(f"Resyncing {len(work_items)} work items")
            yield work_items


@ocean.on_resync(Kind.COLUMN)
async def resync_columns(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for columns in client.get_columns():
            logger.info(f"Resyncing {len(columns)} columns")
            yield columns


@ocean.on_resync(Kind.BOARD)
async def resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for boards in client.get_boards_in_organization():
            logger.info(f"Resyncing {len(boards)} boards")
            yield boards


@ocean.on_resync(Kind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for releases in client.generate_releases():
            logger.info(f"Resyncing {len(releases)} releases")
            yield releases


@ocean.on_resync(Kind.BUILD)
async def resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for builds in client.generate_builds():
            logger.info(f"Resyncing {len(builds)} builds")
            yield builds


@ocean.on_resync(Kind.PIPELINE_STAGE)
async def resync_pipeline_stages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for stages in client.generate_pipeline_stages():
            logger.info(f"Resyncing {len(stages)} pipeline stages")
            yield stages


@ocean.on_resync(Kind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for environments in client.generate_environments():
            logger.info(f"Fetched {len(environments)} environments")
            yield environments


@ocean.on_resync(Kind.RELEASE_DEPLOYMENT)
async def resync_release_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for deployments in client.generate_release_deployments():
            logger.info(f"Fetched {len(deployments)} release deployments")
            yield deployments


@ocean.on_resync(Kind.PIPELINE_DEPLOYMENT)
async def resync_pipeline_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for environments in client.generate_environments():
            tasks = [
                client.generate_pipeline_deployments(
                    environment_id=environment["id"],
                    project=environment["project"],
                )
                for environment in environments
            ]
            async for deployments in stream_async_iterators_tasks(*tasks):
                logger.info(f"Fetched {len(deployments)} pipeline deployments")
                yield deployments


@ocean.on_resync(Kind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsFileResourceConfig, event.resource_config)
    included_files = config.selector.included_files or []

    logger.info(f"Starting file resync for paths: {config.selector.files.path}")

    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for files_batch in client.generate_files(
            path=config.selector.files.path,
            repos=config.selector.files.repos,
        ):
            if files_batch:
                logger.info(f"Resyncing batch of {len(files_batch)} files")
                if included_files:
                    enricher = IncludedFilesEnricher(
                        client=client,
                        strategy=FileIncludedFilesStrategy(
                            included_files=included_files
                        ),
                    )
                    files_batch = await enricher.enrich_batch(files_batch)
                yield files_batch


@ocean.on_resync(Kind.PIPELINE_RUN)
async def resync_pipeline_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for runs in client.generate_pipeline_runs():
            logger.info(f"Resyncing {len(runs)} pipeline runs")
            yield runs


@ocean.on_resync(Kind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    selector = cast(AzureDevopsFolderResourceConfig, event.resource_config).selector
    included_files = selector.included_files or []
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
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


@ocean.on_resync(Kind.TEST_RUN)
async def resync_test_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsTestRunResourceConfig, event.resource_config).selector
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for test_runs in client.fetch_test_runs(
            selector.include_results, selector.code_coverage
        ):
            logger.info(f"Fetched {len(test_runs)} test runs")
            yield test_runs


@ocean.on_resync(Kind.ITERATION)
async def resync_iterations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for iterations in client.generate_iterations():
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

    manager = AzureDevopsClientManager.create_from_ocean_config()
    for client in manager.get_clients():
        async for repositories in client.generate_repositories():
            for repository in repositories:
                async for security_alerts in client.generate_advanced_security_alerts(
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
