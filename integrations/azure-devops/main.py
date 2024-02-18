from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from azure_devops.client import AzureDevopsHTTPClient
from azure_devops.webhooks.webhook_event import WebhookEvent
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from azure_devops.search_criteria import (
    PULL_REQUEST_SEARCH_CRITERIA,
    WORK_ITEMS_WIQL_QUERY,
    MAX_WORK_ITEMS_PER_QUERY,
)
from bootstrap import setup_listeners, webhook_event_handler
from starlette.requests import Request


@ocean.on_start()
async def setup_webhooks() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    if not ocean.integration_config.get("app_host"):
        logger.warning("No app host provided, skipping webhook creation.")
        return

    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    await setup_listeners(ocean.integration_config["app_host"], azure_devops_client)


@ocean.on_resync("project")
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for projects in azure_devops_client.generate_projects():
        logger.debug(f"Resyncing projects: {str(projects)}")
        yield projects


@ocean.on_resync("team")
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for teams in azure_devops_client.generate_teams():
        logger.debug(f"Resyncing teams: {str(teams)}")
        yield teams


@ocean.on_resync("member")
async def resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for members in azure_devops_client.generate_members():
        logger.debug(f"Resyncing members: {str(members)}")
        yield members


@ocean.on_resync("pipeline")
async def resync_pipeline(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for pipelines in azure_devops_client.generate_pipelines():
        logger.debug(f"Resyncing pipelines: {str(pipelines)}")
        yield pipelines


@ocean.on_resync("pull_request")
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    for search_filter in PULL_REQUEST_SEARCH_CRITERIA:
        async for pull_requests in azure_devops_client.generate_pull_requests(
            search_filter
        ):
            logger.debug(f"Resyncing pull_requests: {str([pull_requests])}")
            yield pull_requests


@ocean.on_resync("repository")
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for repositories in azure_devops_client.generate_repositories():
        logger.debug(f"Resyncing repositories: {str([repositories])}")
        yield repositories


@ocean.on_resync("work_item")
async def resync_work_items(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for work_items in azure_devops_client.generate_work_items_by_wiql(
        WORK_ITEMS_WIQL_QUERY, MAX_WORK_ITEMS_PER_QUERY
    ):
        logger.debug(f"Resyncing work items: {str(work_items)}")
        yield work_items


@ocean.on_resync("board")
async def resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for boards in azure_devops_client.generate_boards():
        logger.debug(f"Resyncing boards: {str(boards)}")
        yield boards


@ocean.on_resync("repository_policy")
async def resync_repository_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsHTTPClient.create_from_ocean_config()
    async for policies in azure_devops_client.generate_repository_policies():
        logger.debug(f"Resyncing repository policies: {str(policies)}")
        yield policies


@ocean.router.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    body = await request.json()
    webhook_event = WebhookEvent(
        eventType=body.get("eventType"), publisherId=body.get("publisherId")
    )
    await webhook_event_handler.notify(webhook_event, body)
    return {"ok": True}
