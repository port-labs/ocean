from typing import Any
from loguru import logger
from fastapi import Request
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from gitlab.client import GitLabClient
from gitlab.webhook_handler import WebhookHandler
from gitlab.helpers.utils import ObjectKind, ResourceKindsHandledViaWebhooks

@ocean.on_resync()
async def on_resources_resync(kind: str) -> None:
    logger.info(f"Received re-sync for kind {kind}")

    if kind == ObjectKind.PROJECT:
        return

    gitlab_client = GitLabClient.create_from_ocean_config()

    async for resources in gitlab_client.get_resources(kind):
        logger.info(f"Re-syncing {len(resources)} {kind}")
        yield resources
        return

@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Project Re-sync req received")
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for projects in gitlab_client.get_resources(ObjectKind.PROJECT, {"owned": "yes"}):
        logger.info(f"Re-syncing {len(projects)} projects")
        yield projects
        return

@ocean.router.post("/webhook")
async def on_webhook_alert(request: Request) -> dict[str, Any]:
    body = await request.json()
    event = body.get("object_kind")

    if event in iter(ResourceKindsHandledViaWebhooks):
        webhook_handler = WebhookHandler()
        await webhook_handler.handle_event(event, body)

    return {"status": "success"}

@ocean.on_start()
async def on_start() -> None:
    print("Starting async-gitlab integration...")

    print("Initializing webhook setup...")
    webhook_handler = WebhookHandler()
    await webhook_handler.setup()
