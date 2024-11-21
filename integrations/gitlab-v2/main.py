from typing import Any

from aiolimiter import AsyncLimiter
from fastapi import Request
from loguru import logger

from client import GitLabHandler, get_gitlab_handler
from port_ocean.context.ocean import ocean
from choices import Endpoint, Entity
from webhook import WebhookEventHandler


ENDPOINT_MAP = {
    Entity.GROUP.value: Endpoint.GROUP.value,
    Entity.PROJECT.value: Endpoint.PROJECT.value,
    Entity.MERGE_REQUEST.value: Endpoint.MERGE_REQUEST.value,
    Entity.ISSUE.value: Endpoint.ISSUE.value,
}

RESOURCE_RATE_LIMIT = {
    Entity.GROUP.value: 200,
    Entity.PROJECT.value: 200,
    Entity.MERGE_REQUEST.value: 200,
    Entity.ISSUE.value: 200,
}


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    if kind in ENDPOINT_MAP:
        logger.info(f"Resycing {kind}...")

        limiter = AsyncLimiter(0.8 * RESOURCE_RATE_LIMIT[kind])
        handler: GitLabHandler = await get_gitlab_handler(limiter)
        return await handler.send_gitlab_api_request(ENDPOINT_MAP[kind])

    logger.warning(f"Unsupported kind for resync: {kind}")
    return []


@ocean.router.post("/webhook")
async def gitlab_webhook(request: Request) -> dict[str, bool]:
    payload = await request.json()

    logger.info(f"Received webhook payload: {payload} from gitlab")

    port_headers = request.headers.get("port-headers")
    if not port_headers:
        logger.error(f"Port headers not found in webhook headers: {request.headers}")
        return {"success": False}

    gitlab_handler = await get_gitlab_handler()

    expected_port_headers = gitlab_handler.webhook_secret
    if port_headers != expected_port_headers:
        logger.error("Invalid port headers")
        return {"success": False}

    payload = await request.json()

    webhook_handler = WebhookEventHandler(gitlab_handler)

    event = request.headers.get("X-Gitlab-Event")
    if event == "System Hook":
        entity, payload = await webhook_handler.system_hook_handler(payload)
    else:
        entity, payload = await webhook_handler.group_hook_handler(payload)

    if entity and payload:
        await ocean.register_raw(entity, [payload])
        logger.info("Gitlab Webhook processed successfully.")
    else:
        logger.info(f"Skipped webhook payload: {payload} from gitlab")

    return {"success": True}


@ocean.on_start()
async def on_start() -> None:
    handler: GitLabHandler = await get_gitlab_handler()
    if handler.app_host and handler.webhook_secret:
        logger.info("Fetching group data for webhook...")
        group_list = await handler.send_gitlab_api_request(Endpoint.GROUP.value)

        for group_data in group_list:
            group_id = group_data["id"]
            logger.info(f"Setting up hooks for group: {group_id}...")
            await handler.create_webhook(group_id)
