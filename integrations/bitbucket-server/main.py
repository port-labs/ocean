from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import (
    BitbucketGenericResourceConfig,
    BitbucketPullRequestResourceConfig,
    ObjectKind,
)
from utils import initialize_client


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(BitbucketGenericResourceConfig, event.resource_config).selector
    logger.info(f"Resyncing projects with filter: {selector.projects}")
    client = initialize_client()
    async for project_batch in client.get_projects(projects_filter=selector.projects):
        logger.info(f"Received {len(project_batch)} projects")
        yield project_batch


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(BitbucketGenericResourceConfig, event.resource_config).selector
    logger.info(f"Resyncing repositories for projects: {selector.projects}")
    client = initialize_client()
    async for repo_batch in client.get_repositories(projects_filter=selector.projects):
        logger.info(f"Received {len(repo_batch)} repositories")
        yield repo_batch


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(BitbucketPullRequestResourceConfig, event.resource_config).selector
    logger.info(f"Resyncing pull requests with state: {selector.state}")
    client = initialize_client()
    async for pr_batch in client.get_pull_requests(
        projects_filter=selector.projects, state=selector.state
    ):
        logger.info(f"Received {len(pr_batch)} pull requests")
        yield pr_batch


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Resyncing users")
    client = initialize_client()
    async for user_batch in client.get_users():
        logger.info(f"Received {len(user_batch)} users")
        yield user_batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Bitbucket Server integration")
    logger.info("Performing healthcheck")
    client = initialize_client()
    await client.healthcheck()
    logger.info("Healthcheck passed")
    logger.info("Setting up webhooks")
    if not client.app_host:
        logger.warning("No app host provided, skipping webhook setup")
    else:
        await client.setup_webhooks()
        logger.info("Webhooks set up")
