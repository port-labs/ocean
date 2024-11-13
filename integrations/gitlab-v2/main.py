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

    port_headers = request.headers.get("port-headers")
    if not port_headers:
        return {"success": False}

    payload = await request.json()
    handler = GitLabHandler()

    event = request.headers.get("X-Gitlab-Event")
    if event == "System Hook":
        entity, payload = await handler.system_hook_handler(payload)
    else:
        entity, payload = await handler.webhook_handler(payload)

    await ocean.register_raw(entity, [payload])

    logger.info("Webhook processed successfully.")

    return {"success": True}
