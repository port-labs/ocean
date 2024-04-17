from typing import Any, cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.webhook_event import WebhookEvent
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from bootstrap import setup_listeners, webhook_event_handler
from starlette.requests import Request
from azure_devops.misc import (
    Kind,
    PULL_REQUEST_SEARCH_CRITERIA,
    AzureDevopsProjectResourceConfig,
)


@ocean.on_start()
async def setup_webhooks() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    if not ocean.integration_config.get("app_host"):
        logger.warning("No app host provided, skipping webhook creation.")
        return

    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    await setup_listeners(ocean.integration_config["app_host"], azure_devops_client)


@ocean.on_resync(Kind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()

    selector = cast(AzureDevopsProjectResourceConfig, event.resource_config).selector
    sync_default_team = selector.default_team

    async for projects in azure_devops_client.generate_projects(sync_default_team):
        logger.info(f"Resyncing {len(projects)} projects")
        yield projects


@ocean.on_resync(Kind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for teams in azure_devops_client.generate_teams():
        logger.info(f"Resyncing {len(teams)} teams")
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


@ocean.router.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    body = await request.json()
    webhook_event = WebhookEvent(
        eventType=body.get("eventType"), publisherId=body.get("publisherId")
    )
    await webhook_event_handler.notify(webhook_event, body)
    return {"ok": True}
