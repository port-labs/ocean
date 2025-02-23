from typing import Any
from loguru import logger
from starlette.requests import Request
from client import BitbucketClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from enum import StrEnum

class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PROJECT = "project"
    PULL_REQUEST = "pull-request"
    COMPONENT = "component"


@ocean.on_start()
async def on_start() -> None:
    integration_config = ocean.integration_config
    logger.info(f"Integration config: {integration_config}")

    if "bitbucket_token" not in integration_config:
        logger.error("bitbucket_token is missing in the integration configuration")
        return


# Initialize Bitbucket cloud client
def get_bitbucket_client() -> BitbucketClient:
    bitbucket_token = ocean.integration_config["bitbucket_token"]
    bitbucket_workspace = ocean.integration_config["bitbucket_workspace"]
    return BitbucketClient(bitbucket_workspace, bitbucket_token)

# Resync handler for repositories
@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    repositories = await client.fetch_repositories()
    for repo in repositories:
        yield repo

# Resync handler for projects
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    projects = await client.fetch_projects()
    for project in projects:
        yield project

# Resync handler for pull requests
@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    repositories = await client.fetch_repositories()
    for repo in repositories:
        repo_slug = repo["slug"]
        pull_requests = await client.fetch_pull_requests(repo_slug)
        for pr in pull_requests:
            yield pr

# Resync handler for components
@ocean.on_resync(ObjectKind.COMPONENT)
async def on_resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    repositories = await client.fetch_repositories()
    for repo in repositories:
        repo_slug = repo["slug"]
        components = await client.fetch_components(repo_slug)
        for component in components:
            yield component

# Webhook handler
@ocean.router.post("/webhook")
async def handle_webhook(request: Request):
    event = await request.json()
    logger.info(f"Received webhook event: {event}")
    await ocean.update_entities(event)

# Logging
logger.info("Bitbucket cloud integration is running and ready to fetch data.")