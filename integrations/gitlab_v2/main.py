import typing
from enum import StrEnum
from typing import Any
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import CREATE_UPDATE_WEBHOOK_EVENTS, DELETE_WEBHOOK_EVENTS, GitlabClient


class InvalidTokenException(Exception):
    ...


class ResourceKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"

class WebHookEventType(StrEnum):
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"

EVENT_TYPE_MAPPING = {
    WebHookEventType.MERGE_REQUEST: "merge_requests",
    WebHookEventType.ISSUE: "issues"
}


@ocean.on_start()
async def on_start() -> None:
    logger.info(f"Starting musah_gitlab integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    tokens = ocean.integration_config["gitlab_access_tokens"]["tokens"]
    # Check if tokens is a list and filter valid tokens (strings only)
    if isinstance(tokens, list):
        tokens_are_valid = filter(lambda token: isinstance(token, str), tokens)

        # Ensure all tokens are valid strings
        if not all(tokens_are_valid):
            raise InvalidTokenException("Invalid access tokens, ensure all tokens are valid strings")
    else:
        raise InvalidTokenException("Invalid access tokens, confirm you passed in a list of tokens")

    return await setup_application()


def initialize_client(gitlab_access_token: str) -> GitlabClient:
    return GitlabClient(
        ocean.integration_config["gitlab_host"],
        gitlab_access_token,
    )


async def setup_application() -> None:
    app_host = ocean.integration_config["app_host"]
    tokens = ocean.integration_config["gitlab_access_tokens"]["tokens"]
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Gitlab"
        )
        return

    gitlab_client = initialize_client(tokens[0])
    webhook_uri = f"{app_host}/integration/webhook"

    async for projects in gitlab_client.get_paginated_resources(f"{ResourceKind.PROJECT}s"):
        for project in projects:
            hooks = project.get("__hooks", [])
            webhook_exists = any(
                isinstance(hook, dict) and hook.get("url") == webhook_uri
                for hook in hooks
            )

            if not webhook_exists:
                await gitlab_client.create_project_webhook(webhook_uri, project)
                logger.info(f"Created webhook for project {project['id']}")
            else:
                logger.info(f"Webhook already exists for project {project['id']}")


async def handle_webhook_event(
        webhook_event: str,
        object_attributes_action: str,
        data: dict[str, Any],
) -> dict[str, Any]:
    ocean_action = None
    git_client = initialize_client(ocean.integration_config["gitlab_access_tokens"]["tokens"][0])
    if object_attributes_action in DELETE_WEBHOOK_EVENTS:
        ocean_action = ocean.unregister_raw
    elif object_attributes_action in CREATE_UPDATE_WEBHOOK_EVENTS:
        ocean_action = ocean.register_raw

    if not ocean_action:
        logger.info(f"Webhook event '{webhook_event}' not recognized.")
        return {"ok": True}

    # Map webhook events to their respective handler functions
    event_handlers = {
        "push": handle_push_event,
        "merge_request": handle_merge_request_event,
        "issue": handle_issue_event,
    }

    # Call the appropriate event handler function based on the webhook_event
    handler = event_handlers.get(webhook_event)
    if handler:
        await handler(git_client, ocean_action, data)
    else:
        logger.info(f"Unhandled webhook event type: {webhook_event}")
        return {"ok": True}

    logger.info(f"Webhook event '{webhook_event}' processed successfully.")
    return {"ok": True}


async def handle_push_event(git_client, ocean_action, data: dict[str, Any]) -> None:
    """Handles push webhook event."""
    project_id = data.get("project", {}).get("id")
    project = await git_client.get_single_resource("projects", str(project_id))
    logger.info(f"Upserting project with payload: {data}")
    await ocean_action(ResourceKind.PROJECT, [project])

async def handle_merge_request_event(git_client, ocean_action, data: dict[str, Any]) -> None:
    """Handles merge request webhook event."""
    project_id = data.get("project", {}).get("id")
    mr_iid = data.get("object_attributes", {}).get("iid")
    mr = await git_client.get_single_resource(f"projects/{project_id}/merge_requests", str(mr_iid))
    logger.info(f"Upserting merge request with payload: {data}")
    await ocean_action(ResourceKind.MERGE_REQUEST, [mr])


async def handle_issue_event(git_client, ocean_action, data: dict[str, Any]) -> None:
    """Handles issue webhook event."""
    project_id = data.get("project", {}).get("id")
    issue_iid = data.get("object_attributes", {}).get("iid")
    issue = await git_client.get_single_resource(f"projects/{project_id}/issues", str(issue_iid))
    logger.info(f"Upserting issue with payload: {issue}")
    await ocean_action(ResourceKind.ISSUE, [issue])

@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    webhook_event = data.get("event_type", "")
    object_attributes_action = data.get("object_attributes", {}).get("action", "")
    logger.info(
        f"Received webhook event: {webhook_event} with action: {object_attributes_action}"
    )

    return await handle_webhook_event(webhook_event, object_attributes_action, data)


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tokens = ocean.integration_config["gitlab_access_tokens"]["tokens"]
    for token in tokens:
        gitlab_client = initialize_client(token)
        async for resource_batch in gitlab_client.get_paginated_resources(f"{kind}s"):
            logger.info(f"Received length  {len(resource_batch)} of {kind}s ")
            yield resource_batch
