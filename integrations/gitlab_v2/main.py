import typing
from enum import StrEnum
from typing import Any
from loguru import logger

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


@ocean.on_start()
async def on_start() -> None:
    logger.info(f"Starting musah_gitlab integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    return await setup_application()


# Centralized Token Manager
class TokenManager:
    def __init__(self) -> None:
        self._tokens = ocean.integration_config["gitlab_access_tokens"]["tokens"]
        self.validate_tokens()

    def get_token(self, index: int = 0) -> str:
        if index >= len(self._tokens):
            raise InvalidTokenException("Requested token index is out of range")
        return self._tokens[index]

    def get_tokens(self) -> list[str]:
        """Public method to access tokens"""
        return self._tokens

    def validate_tokens(self) -> None:
        if not isinstance(self._tokens, list):
            raise InvalidTokenException("Invalid access tokens, confirm you passed in a list of tokens")

        # Filter valid tokens (strings only) and ensure all are valid
        tokens_are_valid = filter(lambda token: isinstance(token, str), self._tokens)
        if not all(tokens_are_valid):
            raise InvalidTokenException("Invalid access tokens, ensure all tokens are valid strings")

token_manager = TokenManager()

@ocean.on_start()
async def on_start() -> None:
    logger.info(f"Starting musah_gitlab integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    return await setup_application()


def initialize_client(gitlab_access_token: str = None) -> GitlabClient:
    token = gitlab_access_token or token_manager.get_token(0)  # Default to first token

    return GitlabClient(
        ocean.integration_config["gitlab_host"],
        token,
    )


async def setup_application() -> None:
    app_host = ocean.integration_config["app_host"]
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Gitlab"
        )
        return

    gitlab_client = initialize_client()
    webhook_uri = f"{app_host}/integration/webhook"

    await create_webhooks_for_projects(gitlab_client, webhook_uri)
    await create_webhooks_for_groups(gitlab_client, webhook_uri)

async def create_webhooks_for_groups(gitlab_client: GitlabClient, webhook_uri: str) -> None:
    async for groups in gitlab_client.get_paginated_resources(f"{ResourceKind.GROUP}s"):
        for group in groups:
            if not webhook_exists_for_group(group, webhook_uri):
                await gitlab_client.create_group_webhook(webhook_uri, group)
                logger.info(f"Created webhook for group {group['id']}")
            else:
                logger.info(f"Webhook already exists for group {group['id']}")


def webhook_exists_for_group(project: dict[str, Any], webhook_uri: str) -> bool:
    hooks = project.get("__hooks", [])
    return any(
        isinstance(hook, dict) and hook.get("url") == webhook_uri
        for hook in hooks
    )


async def create_webhooks_for_projects(gitlab_client: GitlabClient, webhook_uri: str) -> None:
    async for projects in gitlab_client.get_paginated_resources(f"{ResourceKind.PROJECT}s"):
        for project in projects:
            if not webhook_exists_for_project(project, webhook_uri):
                await gitlab_client.create_project_webhook(webhook_uri, project)
                logger.info(f"Created webhook for project {project['id']}")
            else:
                logger.info(f"Webhook already exists for project {project['id']}")


def webhook_exists_for_project(project: dict[str, Any], webhook_uri: str) -> bool:
    hooks = project.get("__hooks", [])
    return any(
        isinstance(hook, dict) and hook.get("url") == webhook_uri
        for hook in hooks
    )


async def handle_webhook_event(
        webhook_event: str,
        object_attributes_action: str,
        data: dict[str, Any],
) -> dict[str, Any]:
    git_client = initialize_client()
    ocean_action = determine_ocean_action(object_attributes_action)

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
        project_id = data.get("project", {}).get("id")
        await handler(project_id, git_client, ocean_action, data)
    else:
        logger.info(f"Unhandled webhook event type: {webhook_event}")
        return {"ok": True}

    logger.info(f"Webhook event '{webhook_event}' processed successfully.")
    return {"ok": True}


def determine_ocean_action(object_attributes_action: str) -> typing.Callable | None:
    if object_attributes_action in DELETE_WEBHOOK_EVENTS:
        return ocean.unregister_raw
    elif object_attributes_action in CREATE_UPDATE_WEBHOOK_EVENTS:
        return ocean.register_raw
    return None


async def handle_push_event(project_id, git_client, ocean_action, data: dict[str, Any]) -> None:
    """Handles push webhook event."""
    project = await git_client.get_single_resource("projects", str(project_id))
    logger.info(f"Upserting project with payload: {data}")
    await ocean_action(ResourceKind.PROJECT, [project])


async def handle_merge_request_event(project_id, git_client, ocean_action, data: dict[str, Any]) -> None:
    """Handles merge request webhook event."""
    mr_iid = data.get("object_attributes", {}).get("iid")
    mr = await git_client.get_single_resource(f"projects/{project_id}/merge_requests", str(mr_iid))
    logger.info(f"Upserting merge request with payload: {data}")
    await ocean_action(ResourceKind.MERGE_REQUEST, [mr])


async def handle_issue_event(project_id, git_client, ocean_action, data: dict[str, Any]) -> None:
    """Handles issue webhook event."""
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
    kind_configs = ocean.integration_config.get("gitlab_resources_config", {}).get(f"{kind}s", {})
    if not kind_configs:
        logger.info(f"Resync initiated for '{kind}', but no additional enrichment configurations were found. Proceeding with the default resync process.")

    for token_index, token in enumerate(token_manager.get_tokens()):
        gitlab_client = initialize_client(token)
        async for resource_batch in gitlab_client.get_paginated_resources(f"{kind}s", kind_configs):
            logger.info(f"Received batch of {len(resource_batch)} {kind}s with token {token_index}")
            yield resource_batch
