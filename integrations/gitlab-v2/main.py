from typing import Any

from fastapi import Request
from loguru import logger

from client import GitLabHandler
from port_ocean.context.ocean import ocean


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


# The same sync logic can be registered for one of the kinds that are available in the mapping in port.
@ocean.on_resync("group")
async def resync_group(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all groups from the source system
    # 2. Return a list of dictionaries with the raw data of the state
    handler = GitLabHandler()
    return await handler.fetch_data("/groups")


@ocean.on_resync("project")
async def resync_project(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all projects from the source system
    # 2. Return a list of dictionaries with the raw data of the state
    handler = GitLabHandler()
    return await handler.fetch_data("/projects?membership=yes")


@ocean.on_resync("merge-request")
async def resync_merge_request(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all merge requests from the source system
    # 2. Return a list of dictionaries with the raw data of the state
    handler = GitLabHandler()
    return await handler.fetch_data("/merge_requests")


@ocean.on_resync("issue")
async def resync_issues(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all issues from the source system
    # 2. Return a list of dictionaries with the raw data of the state
    handler = GitLabHandler()
    return await handler.fetch_data("/issues")


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting gitlab-v2 integration")
