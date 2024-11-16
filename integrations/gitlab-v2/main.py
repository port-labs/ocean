from typing import Any

from aiolimiter import AsyncLimiter
from fastapi import Request
from loguru import logger

from client import GitLabHandler
from port_ocean.context.ocean import ocean
from choices import Endpoint, Entity


ENDPOINT_MAP = {
    Entity.GROUP.value: Endpoint.GROUP.value,
    Entity.PROJECT.value: Endpoint.PROJECT.value,
    Entity.MERGE_REQUEST.value: Endpoint.MERGE_REQUEST.value,
    Entity.ISSUE.value: Endpoint.ISSUE.value,
}


async def get_limiter(entity: str) -> AsyncLimiter:
    if entity == Entity.GROUP.value:
        rate_limit = ocean.integration_config.get("group_ratelimit", 200)
    elif entity == Entity.PROJECT.value:
        rate_limit = ocean.integration_config.get("project_ratelimit", 200)
    elif entity == Entity.MERGE_REQUEST.value:
        rate_limit = ocean.integration_config.get("mergerequest_ratelimit", 200)
    else:
        rate_limit = ocean.integration_config.get("issue_ratelimit", 200)

    return AsyncLimiter(0.8 * rate_limit)


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    if kind in ENDPOINT_MAP:
        logger.info(f"Resycing {kind} from Gitlab...")

        limiter = await get_limiter(kind)

        handler = GitLabHandler(
            host=ocean.integration_config["app_host"],
            gitlab_token=ocean.integration_config["gitlab_token"],
            gitlab_url=ocean.integration_config["gitlab_url"],
            webhook_secret=ocean.integration_config["webhook_secret"],
            rate_limit=limiter,
        )
        return await handler.fetch_data(ENDPOINT_MAP[kind])

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

    payload = await request.json()
    handler = GitLabHandler(
        host=ocean.integration_config["app_host"],
        gitlab_token=ocean.integration_config["gitlab_token"],
        gitlab_url=ocean.integration_config["gitlab_url"],
        webhook_secret=ocean.integration_config["webhook_secret"],
        rate_limit=AsyncLimiter(0.8 * 200),
    )

    event = request.headers.get("X-Gitlab-Event")
    if event == "System Hook":
        entity, payload = await handler.system_hook_handler(payload)
    else:
        entity, payload = await handler.group_hook_handler(payload)

    if entity and payload:
        await ocean.register_raw(entity, [payload])
        logger.info("Gitlab Webhook processed successfully.")
    else:
        logger.info(f"Skipped webhook payload: {payload} from gitlab")

    return {"success": True}
