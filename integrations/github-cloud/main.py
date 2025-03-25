from typing import Any, AsyncGenerator
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from port_ocean.context.ocean import ocean
from client import GithubHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@ocean.on_resync('repository')
async def resync_repository(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync repositories."""
    try:
        handler = GithubHandler()
        async for repo in handler.get_repositories():
            logger.info(f"Yielding repository: {repo['name']}")
            yield repo
    except Exception as e:
        logger.error(f"Failed to resync repository: {e}")

@ocean.on_resync('issue')
async def resync_issues(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync issues."""
    try:
        handler = GithubHandler()
        async for repo in handler.get_repositories():
            async for issue in handler.get_issues(repo["owner"]["login"], repo["name"]):
                logger.info(f"Yielding issue: {issue['title']}")
                yield issue
    except Exception as e:
        logger.error(f"Failed to resync issues: {e}")

@ocean.on_resync('pull_request')
async def resync_pull_requests(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync pull requests."""
    try:
        handler = GithubHandler()
        async for repo in handler.get_repositories():
            async for pull_request in handler.get_pull_requests(repo["owner"]["login"], repo["name"]):
                logger.info(f"Yielding pull request: {pull_request['title']}")
                yield pull_request
    except Exception as e:
        logger.error(f"Failed to resync pull requests: {e}")

@ocean.on_resync('team')
async def resync_teams(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync teams."""
    try:
        handler = GithubHandler()
        async for org in handler.get_organizations():
            async for team in handler.get_teams(org["login"]):
                logger.info(f"Yielding team: {team['name']}")
                yield team
    except Exception as e:
        logger.error(f"Failed to resync teams: {e}")

@ocean.on_resync('workflow')
async def resync_workflows(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync workflows."""
    try:
        handler = GithubHandler()
        async for repo in handler.get_repositories():
            async for workflow in handler.get_workflows(repo["owner"]["login"], repo["name"]):
                logger.info(f"Yielding workflow: {workflow['name']}")
                yield workflow
    except Exception as e:
        logger.error(f"Failed to resync workflows: {e}")

@ocean.on_start()
async def on_start() -> None:
    """Handle integration start."""
    logger.info("Starting GitHub Cloud integration")