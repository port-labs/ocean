import typing
from typing import Any
from loguru import logger
from client import GitLabClient
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind:
    GROUP = "group"
    MERGE_REQUEST = "merge-request"
    ISSUE = "issues"
    PROJECT = "projects"


def init_gitlab_client() -> GitLabClient:
    """Initialize GitLab client with configuration values."""
    return GitLabClient(
        ocean.integration_config["gitlab_api_url"],
        ocean.integration_config["gitlab_token"]
    )


@ocean.on_resync(ObjectKind.GROUP)
async def resync_group_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = init_gitlab_client()

    async for groups in gitlab_client.get_groups():
        logger.info(f"Received batch with {len(groups)} groups")
        yield groups


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_request_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = init_gitlab_client()

    async for merge_requests in gitlab_client.get_merge_requests():
        logger.info(f"Received batch with {len(merge_requests)} merge requests")
        yield merge_requests


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issue_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = init_gitlab_client()

    async for issues in gitlab_client.get_issues():
        logger.info(f"Received batch with {len(issues)} issues")
        yield issues


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_project_handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = init_gitlab_client()

    async for projects in gitlab_client.get_projects():
        logger.info(f"Received batch with {len(projects)} projects")
        yield projects


@ocean.router.post("/webhook")
async def handle_webhook(data: dict[str, Any]) -> dict[str, Any]:
    """Handle incoming webhook events."""
    logger.info(f"Received event type {data['object_kind']} - Event ID: {data['object_attributes']['id']}")

    gitlab_client = init_gitlab_client()

    if data["object_kind"] == "merge_request":
        merge_request = await gitlab_client.get_single_merge_request(data["object_attributes"]["id"])
        if merge_request:
            logger.info(f"Updating merge request with ID {merge_request['id']}")
            await ocean.register_raw(ObjectKind.MERGE_REQUEST, [merge_request])

    elif data["object_kind"] == "issue":
        issue = await gitlab_client.get_single_issue(data["object_attributes"]["id"])
        if issue:
            logger.info(f"Updating issue with ID {issue['id']}")
            await ocean.register_raw(ObjectKind.ISSUE, [issue])

    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    """Setup GitLab webhook on integration start."""
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    app_host = ocean.integration_config.get("app_host")
    webhook_token = ocean.integration_config.get("gitlab_token")

    if app_host and webhook_token:
        gitlab_client = init_gitlab_client()

        # Set up group-level webhook
        await setup_group_webhooks(gitlab_client, app_host, webhook_token)

        # Set up project-level webhooks for all projects in the group
        await setup_project_webhooks(gitlab_client, app_host, webhook_token)

    else:
        logger.warning("Missing app_host or gitlab_token, skipping webhook setup.")


async def setup_group_webhooks(gitlab_client: GitLabClient, app_host: str, webhook_token: str) -> None:
    """Setup GitLab webhooks for all groups."""
    async for groups in gitlab_client.get_groups():
        for group in groups:
            group_id = group["id"]
            logger.info(f"Setting up webhook for group {group['name']} (ID: {group_id})")
            endpoint = f"groups/{group_id}/hooks"
            webhook_url = f"{app_host}/webhook"
            payload = {
                "url": webhook_url,
                "token": webhook_token,
                "push_events": True,
                "merge_requests_events": True,
                "issues_events": True,
            }
            await gitlab_client._request("POST", endpoint, json=payload)


async def setup_project_webhooks(gitlab_client: GitLabClient, app_host: str, webhook_token: str) -> None:
    """Setup GitLab webhooks for all projects."""
    async for projects in gitlab_client.get_projects():
        for project in projects:
            project_id = project["id"]
            logger.info(f"Setting up webhook for project {project['name']} (ID: {project_id})")
            endpoint = f"projects/{project_id}/hooks"
            webhook_url = f"{app_host}/webhook"
            payload = {
                "url": webhook_url,
                "token": webhook_token,
                "push_events": True,
                "merge_requests_events": True,
                "issues_events": True,
            }
            await gitlab_client._request("POST", endpoint, json=payload)
