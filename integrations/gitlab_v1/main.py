from enum import StrEnum
from typing import Any, Dict, List, Callable, AsyncGenerator
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import GitlabHandler
from loguru import logger
from fastapi import Request, HTTPException


WEBHOOK_SECRET = ocean.integration_config.get('webhook_secret')
WEBHOOK_URL = ocean.integration_config.get('webhook_url')


# Define ObjectKind for GitLab
class ObjectKind(StrEnum):
    GROUP = "gitlabGroup"
    PROJECT = "gitlabProject"
    MERGE_REQUEST = "gitlabMergeRequest"
    ISSUE = "gitlabIssue"


async def fetch_resource(fetch_method: Callable[[], AsyncGenerator[Dict[str, Any], None]]) -> List[Dict[str, Any]]:
    """Fetch resources using the provided fetch method."""
    items = []
    try:
        async for item in fetch_method():
            logger.info(f"Received item: {item}")
            items.append(item)
    except Exception as e:
        logger.error(f"Error fetching resources: {str(e)}")
    return items

@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resynchronization for GitLab groups."""
    if kind != ObjectKind.GROUP:
        logger.warning(f"Unexpected kind {kind} for on_resync_groups")
        return []

    if not hasattr(ocean, 'gitlab_handler'):
        logger.error("GitLab handler not initialized. Please check on_start function.")
        return []


    fetch_method = lambda: ocean.gitlab_handler.fetch_resources(ObjectKind.GROUP)
    items = await fetch_resource(fetch_method)
    return items


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resynchronization for GitLab projects."""
    if kind != ObjectKind.PROJECT:
        logger.warning(f"Unexpected kind {kind} for on_resync_projects")
        return []

    if not hasattr(ocean, 'gitlab_handler'):
        logger.error("GitLab handler not initialized. Please check on_start function.")
        return []


    fetch_method = lambda: ocean.gitlab_handler.fetch_resources(ObjectKind.PROJECT)
    items = await fetch_resource(fetch_method)
    return items


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resynchronization for GitLab merge requests."""
    if kind != ObjectKind.MERGE_REQUEST:
        logger.warning(f"Unexpected kind {kind} for on_resync_merge_requests")
        return []

    if not hasattr(ocean, 'gitlab_handler'):
        logger.error("GitLab handler not initialized. Please check on_start function.")
        return []


    fetch_method = lambda: ocean.gitlab_handler.fetch_resources(ObjectKind.MERGE_REQUEST)
    items = await fetch_resource(fetch_method)
    return items


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resynchronization for GitLab issues."""
    if kind != ObjectKind.ISSUE:
        logger.warning(f"Unexpected kind {kind} for on_resync_issues")
        return []

    if not hasattr(ocean, 'gitlab_handler'):
        logger.error("GitLab handler not initialized. Please check on_start function.")
        return []


    fetch_method = lambda: ocean.gitlab_handler.fetch_resources(ObjectKind.ISSUE)
    items = await fetch_resource(fetch_method)
    return items


@ocean.on_start()
async def on_start() -> None:
    """Initialize the GitLab handler."""
    private_token = ocean.integration_config.get('token')
    if not private_token:
        logger.error("GitLab Token not provided in configuration")
        return

    try:
        ocean.gitlab_handler = GitlabHandler(private_token)
        logger.info("GitLab integration started and handler initialized")

        await setup_webhooks()
    except Exception as e:
        logger.error(f"Failed to initialize GitLab handler: {str(e)}")

async def setup_webhooks():
    """Set up webhooks for the GitLab integration."""
    events = ["push", "merge_requests", "issues"]


    if not WEBHOOK_SECRET:
        logger.error("Webhook secret not provided in configuration")
        return


    try:
        await ocean.gitlab_handler.setup_webhooks(WEBHOOK_URL, WEBHOOK_SECRET, events)
        logger.info("Webhooks set up successfully")
    except Exception as e:
        logger.error(f"Failed to set up webhooks: {str(e)}")


@ocean.router.post("/webhook/gitlab")
async def gitlab_webhook(request: Request):
    """Handle incoming GitLab webhook events."""
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhook secret not configured")


    # Verify the webhook signature
    gitlab_token = request.headers.get("X-Gitlab-Token")
    if not gitlab_token or gitlab_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


    payload = await request.json()
    event_type = payload.get("object_kind")


    if event_type == "push":
        await handle_push_event(payload)
    elif event_type == "merge_request":
        await handle_merge_request_event(payload)
    elif event_type == "issue":
        await handle_issue_event(payload)
    else:
        logger.warning(f"Unhandled event type: {event_type}")


    return {"status": "success"}


async def handle_push_event(payload: Dict[str, Any]):
    """Handle push events from GitLab."""
    project_id = payload.get("project", {}).get("id")
    if project_id:
        # Fetch the latest project data and update Port
        project = await ocean.gitlab_handler.get_single_resource("projects", str(project_id))
        mapped_project = ocean.gitlab_handler.mapper_factory.get_mapper(ObjectKind.PROJECT).map(project)
        await ocean.register_raw(ObjectKind.PROJECT, mapped_project)
        logger.info(f"Updated project {project_id} in Port")


async def handle_merge_request_event(payload: Dict[str, Any]):
    """Handle merge request events from GitLab."""
    mr_id = payload.get("object_attributes", {}).get("id")
    project_id = payload.get("project", {}).get("id")
    if mr_id and project_id:
        # Fetch the latest merge request data and update Port
        mr = await ocean.gitlab_handler.get_single_resource(f"projects/{project_id}/merge_requests", str(mr_id))
        mapped_mr = ocean.gitlab_handler.mapper_factory.get_mapper(ObjectKind.MERGE_REQUEST).map(mr)
        await ocean.register_raw(ObjectKind.MERGE_REQUEST, mapped_mr)
        logger.info(f"Updated merge request {mr_id} in Port")


async def handle_issue_event(payload: Dict[str, Any]):
    """Handle issue events from GitLab."""
    issue_id = payload.get("object_attributes", {}).get("id")
    project_id = payload.get("project", {}).get("id")
    if issue_id and project_id:
        # Fetch the latest issue data and update Port
        issue = await ocean.gitlab_handler.get_single_resource(f"projects/{project_id}/issues", str(issue_id))
        mapped_issue = ocean.gitlab_handler.mapper_factory.get_mapper(ObjectKind.ISSUE).map(issue)
        await ocean.register_raw(ObjectKind.ISSUE, mapped_issue)
        logger.info(f"Updated issue {issue_id} in Port")
