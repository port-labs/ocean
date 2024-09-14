from typing import Any, List, Dict, Callable, AsyncGenerator
from port_ocean.context.ocean import ocean
from client import GitlabHandler
from loguru import logger


async def fetch_items(fetch_method: Callable[[], AsyncGenerator[Dict[str, Any], None]]) -> List[Dict[str, Any]]:
    return [item async for item in fetch_method()]


@ocean.on_resync()
async def on_resync(kind: str) -> List[Dict[str, Any]]:
    if not hasattr(ocean, 'gitlab_handler'):
        logger.error("GitLab handler not initialized. Please check on_start function.")
        return []

    resource_map = {
        "gitlabGroup": ocean.gitlab_handler.fetch_groups,
        "gitlabProject": ocean.gitlab_handler.fetch_projects,
        "gitlabMergeRequest": ocean.gitlab_handler.fetch_merge_requests,
        "gitlabIssue": ocean.gitlab_handler.fetch_issues,
    }

    fetch_method = resource_map.get(kind)
    if not fetch_method:
        logger.warning(f"Unknown resource kind: {kind}")
        return []


    try:
        return await fetch_items(fetch_method)
    except Exception as e:
        logger.error(f"Error fetching {kind}: {str(e)}")
        return []


@ocean.on_start()
async def on_start() -> None:
    private_token = ocean.integration_config.get('token')
    if not private_token:
        logger.error("GitLab Token not provided in configuration")
        return

    try:
        ocean.gitlab_handler = GitlabHandler(private_token)
        logger.info("GitLab integration started and handler initialized")
    except Exception as e:
        logger.error(f"Failed to initialize GitLab handler: {str(e)}")
