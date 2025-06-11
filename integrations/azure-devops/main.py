from typing import cast

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.misc import (
    PULL_REQUEST_SEARCH_CRITERIA,
    Kind,
    AzureDevopsFolderResourceConfig,
)
from integration import (
    AzureDevopsProjectResourceConfig,
    AzureDevopsFileResourceConfig,
    AzureDevopsTeamResourceConfig,
    AzureDevopsWorkItemResourceConfig,
)

from azure_devops.webhooks.webhook_processors.pull_request_processor import (
    PullRequestWebhookProcessor,
)

from azure_devops.webhooks.webhook_processors.repository_processor import (
    RepositoryWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.gitops_webhook_processor import (
    GitopsWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


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


@ocean.on_resync(Kind.PIPELINE)
async def resync_pipeline(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for pipelines in azure_devops_client.generate_pipelines():
        logger.info(f"Resyncing {len(pipelines)} pipelines")
        yield pipelines


@ocean.on_resync(Kind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    for search_filter in PULL_REQUEST_SEARCH_CRITERIA:
        async for pull_requests in azure_devops_client.generate_pull_requests(
            search_filter
        ):
            logger.info(f"Resyncing {len(pull_requests)} pull_requests")
            yield pull_requests


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()

    async for repositories in azure_devops_client.generate_repositories():
        logger.info(f"Resyncing {len(repositories)} repositories")
        yield repositories


@ocean.on_resync(Kind.REPOSITORY_POLICY)
async def resync_repository_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for policies in azure_devops_client.generate_repository_policies():
        logger.info(f"Resyncing repository {len(policies)} policies")
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


@ocean.on_resync(Kind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    config = cast(AzureDevopsFileResourceConfig, event.resource_config)

    logger.info(f"Starting file resync for paths: {config.selector.files.path}")

    async for files_batch in azure_devops_client.generate_files(
        path=config.selector.files.path,
        repos=config.selector.files.repos,
    ):
        if files_batch:
            logger.info(f"Resyncing batch of {len(files_batch)} files")
            yield files_batch


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
    async for matching_folders in azure_devops_client.process_folder_patterns(
        selector.folders, selector.project_name
    ):
        yield matching_folders


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", FileWebhookProcessor)
ocean.add_webhook_processor("/webhook", GitopsWebhookProcessor)
ocean.add_webhook_processor("/webhook", FolderWebhookProcessor)
