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
    return

@ocean.on_resync(ObjectKind.GROUP)
async def on_group_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Group Re-sync req received")
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for groups in gitlab_client.get_resources(ObjectKind.GROUP):
        logger.info(f"Re-syncing {len(groups)} groups")
        yield groups
        return

@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Project Re-sync req received")
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for projects in gitlab_client.get_resources(ObjectKind.PROJECT, {"owned": "yes"}):
        logger.info(f"Re-syncing {len(projects)} projects")
        yield projects
        return

@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_merge_request_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for merge_requests in gitlab_client.get_resources(ObjectKind.MERGE_REQUEST):
        logger.info(f"Re-syncing {len(merge_requests)} merge requests")
        yield merge_requests
        return

@ocean.on_resync(ObjectKind.ISSUE)
async def on_issue_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for issues in gitlab_client.get_resources(ObjectKind.ISSUE):
        logger.info(f"Re-syncing {len(issues)} issues")
        yield issues
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
    print("Starting async-gitlab integration")
