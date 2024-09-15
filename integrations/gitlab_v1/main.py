from enum import StrEnum
from typing import Any, Dict, List, Callable, AsyncGenerator
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import GitlabHandler
from loguru import logger


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
    except Exception as e:
        logger.error(f"Failed to initialize GitLab handler: {str(e)}")
