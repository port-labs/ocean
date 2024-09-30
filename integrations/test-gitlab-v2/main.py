from typing import Any
from loguru import logger
from client import GitLabClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from handlers import (
    resync_handler,
    handle_webhook_event,
    setup_webhooks
)
from constants import ObjectKind


def init_gitlab_client() -> GitLabClient:
    """Initialize GitLab client with configuration values."""
    return GitLabClient(
        ocean.integration_config["gitlab_api_url"],
        ocean.integration_config["gitlab_token"]
    )


@ocean.on_resync(ObjectKind.GROUP)
async def resync_group_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    return resync_handler(init_gitlab_client(), kind, "get_groups")


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_request_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    return resync_handler(init_gitlab_client(), kind, "get_merge_requests")


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issue_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    return resync_handler(init_gitlab_client(), kind, "get_issues")


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_project_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    return resync_handler(init_gitlab_client(), kind, "get_projects")


@ocean.router.post("/webhook")
async def handle_webhook(data: dict[str, Any]) -> dict[str, Any]:
    return await handle_webhook_event(init_gitlab_client(), data)


@ocean.on_start()
async def on_start() -> None:
    """Setup GitLab webhook on integration start."""
    app_host = ocean.integration_config.get("app_host")
    webhook_token = ocean.integration_config.get("gitlab_token")
    
    if not app_host or not webhook_token:
        logger.warning("Missing app_host or gitlab_token, skipping webhook setup.")
        return

    if ocean.event_listener_type != "ONCE":
        await setup_webhooks(init_gitlab_client(), app_host, webhook_token)
    else:
        logger.info("Skipping webhook creation because the event listener is ONCE")
