from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import GitLabClient


def init_gitlab_client() -> GitLabClient:
    """Initialize GitLab client with configuration values from ocean config."""
    return GitLabClient(
        base_url=ocean.integration_config["gitlab_api_url"],
        token=ocean.integration_config["gitlab_token"]
    )


async def resync_handler(gitlab_client: GitLabClient, kind: str, method_name: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync for GitLab entities."""
    gitlab_method = getattr(gitlab_client, method_name)  # Retrieve async generator method dynamically

    logger.info(f"Starting resync for {kind}")
    
    async for data_batch in gitlab_method():  # Correctly handling the async generator
        logger.info(f"Received batch with {len(data_batch)} {kind}")
        logger.info(f"Received batch {kind} data {data_batch}")
        yield data_batch


async def handle_webhook_event(data: dict[str, Any]) -> dict[str, Any]:
    """Handle incoming webhook events."""
    gitlab_client = init_gitlab_client()  # Initialize the client locally in the function
    
    logger.info(f"Received event type {data['object_kind']} - Event ID: {data['object_attributes']['id']}")

    object_kind = data["object_kind"]
    object_id = data["object_attributes"]["id"]

    if object_kind == "merge_request":
        merge_request = await gitlab_client.get_single_merge_request(object_id)
        if merge_request:
            logger.info(f"Updating merge request with ID {merge_request['id']}")
            await ocean.register_raw("merge-request", [merge_request])

    elif object_kind == "issue":
        issue = await gitlab_client.get_single_issue(object_id)
        if issue:
            logger.info(f"Updating issue with ID {issue['id']}")
            await ocean.register_raw("issues", [issue])

    return {"ok": True}


async def setup_webhooks(gitlab_client: GitLabClient, app_host: str, webhook_token: str) -> None:
    """Setup webhooks for both groups and projects."""
    await setup_entity_webhooks(gitlab_client.get_groups, "groups", app_host, webhook_token)
    await setup_entity_webhooks(gitlab_client.get_projects, "projects", app_host, webhook_token)



async def setup_entity_webhooks(
    fetch_entities_method: Any,
    entity_name: str,
    app_host: str,
    webhook_token: str
) -> None:
    """Helper to setup webhooks for groups or projects."""
    gitlab_client = init_gitlab_client()  # Initialize the client inside the function
    webhook_url = f"{app_host}/webhook"
    payload = {
        "url": webhook_url,
        "token": webhook_token,
        "push_events": True,
        "merge_requests_events": True,
        "issues_events": True,
    }

    async for entities in fetch_entities_method():
        for entity in entities:
            entity_id = entity["id"]
            logger.info(f"Setting up webhook for {entity_name} {entity['name']} (ID: {entity_id})")
            endpoint = f"{entity_name}/{entity_id}/hooks"
            await gitlab_client._request("POST", endpoint, json=payload)
