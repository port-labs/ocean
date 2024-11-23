from fastapi import Request
from loguru import logger

from client import GitLabHandler, get_gitlab_handler
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from choices import Endpoint, Entity
from webhook import WebhookEventHandler


ENDPOINT_MAP = {
    Entity.GROUP.value: Endpoint.GROUP.value,
    Entity.PROJECT.value: Endpoint.PROJECT.value,
    Entity.MERGE_REQUEST.value: Endpoint.MERGE_REQUEST.value,
    Entity.ISSUE.value: Endpoint.ISSUE.value,
}


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind not in ENDPOINT_MAP:
        logger.warning(f"Unsupported kind for resync: {kind}")
        return

    logger.info(f"Resycing {kind}...")

    handler: GitLabHandler = await get_gitlab_handler()
    query_params = {"membership": "yes"} if kind == Entity.PROJECT.value else None
    async for record in handler.get_paginated_resource(
        ENDPOINT_MAP[kind], query_params=query_params
    ):
        yield record


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
        logger.info("Fetching group data for webhook creation...")

        group_records = await handler.get_all_resource(
            f"{Endpoint.GROUP.value}?owned=yes"
        )
        for group_data in group_records:
            group_id = group_data["id"]
            logger.info(f"Setting up hooks for group: {group_id}...")
            await handler.create_webhook(group_id)
