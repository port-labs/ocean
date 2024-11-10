from typing import Any

from fastapi import Request
from loguru import logger

from client import GitLabHandler
from port_ocean.context.ocean import ocean
from choices import Endpoint, Entity


ENDPOINTS = {
    Entity.GROUP.value: Endpoint.GROUP.value,
    Entity.PROJECT.value: Endpoint.PROJECT.value,
    Entity.MERGE_REQUEST.value: Endpoint.MERGE_REQUEST.value,
    Entity.ISSUE.value: Endpoint.ISSUE.value,
}


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    """
    Resync handler based on entity kind. Supports project, group, merge_request, and issue kinds.
    """

    if kind in ENDPOINTS:
        logger.info(f"Resycing {kind} from Gitlab...")
        handler = GitLabHandler()
        return await handler.fetch_data(ENDPOINTS[kind])

    logger.warning(f"Unsupported kind for resync: {kind}")
    return []


@ocean.router.post("/webhook")
async def gitlab_webhook(request: Request) -> dict[str, bool]:
    payload = await request.json()

    logger.info(
        f"Received payload: {payload} and headers {request.headers} from gitlab"
    )

    webhook_secret = ocean.integration_config.get("gitlab_secret")
    secret_key = request.headers.get("X-Gitlab-Token")
    if not secret_key or secret_key != webhook_secret:
        return {"success": False}

    payload = await request.json()
    handler = GitLabHandler()

    event = request.headers.get("X-Gitlab-Event")
    if event == "System Hook":
        # Handles project and groups
        await handler.system_hook_handler(payload)
    else:
        # Handles merge request and issues
        await handler.webhook_handler(payload)

    logger.info("Webhook processed successfully.")

    return {"success": True}
