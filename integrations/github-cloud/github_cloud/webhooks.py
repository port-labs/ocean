import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from port_ocean.context.ocean import ocean
from client import GithubHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def manage_webhooks() -> None:
    """Manage webhooks for all repositories."""
    handler = GithubHandler()
    async for repo in handler.get_repositories():
        owner = repo["owner"]["login"]
        repo_name = repo["name"]

        if not repo_name or repo_name.startswith("-"):
            logger.error(f"Invalid repository name: {repo_name}")
            continue

        logger.info(f"Processing repository: {repo_name} owned by {owner}")

        try:
            existing_hook = await get_webhook_for_repo(handler, owner, repo_name)
            if existing_hook:
                if existing_hook.get("active") is False:
                    logger.info(f"Reactivating webhook for {owner}/{repo_name}")
                    await delete_webhook_for_repo(handler, owner, repo_name, existing_hook["id"])
                    await create_webhook_for_repo(handler, owner, repo_name)
            else:
                await create_webhook_for_repo(handler, owner, repo_name)
        except Exception as e:
            logger.error(f"Error managing webhook for {owner}/{repo_name}: {e}")

async def get_webhook_for_repo(handler: GithubHandler, owner: str, repo: str) -> dict | None:
    """Check if a webhook exists for a repository."""
    url = f"{handler.base_url}/repos/{owner}/{repo}/hooks"
    hooks = await handler.fetch_with_retry(url)
    app_hook_url = f"{handler.app_host}/integration/hook/github-cloud"
    for hook in hooks:
        if hook["config"].get("url") == app_hook_url:
            logger.info(f"Found existing webhook for {owner}/{repo} with ID {hook['id']}")
            return hook
    return None

async def create_webhook_for_repo(handler: GithubHandler, owner: str, repo: str) -> None:
    """Create a webhook for a repository."""
    url = f"{handler.base_url}/repos/{owner}/{repo}/hooks"
    payload = {
        "name": "web",
        "active": True,
        "events": ["push", "pull_request", "issues"],
        "config": {
            "url": f"{handler.app_host}/integration/hook/github-cloud",
            "content_type": "json",
            "insecure_ssl": "0",
        },
    }
    try:
        response = await handler.client.post(url, headers=handler.headers, json=payload)
        if response.status_code == 201:
            logger.info(f"Webhook created for {owner}/{repo}")
        else:
            logger.error(f"Failed to create webhook for {owner}/{repo}: {response.text}")
    except Exception as e:
        logger.error(f"Error creating webhook for {owner}/{repo}: {e}")

async def delete_webhook_for_repo(handler: GithubHandler, owner: str, repo: str, hook_id: int) -> None:
    """Delete a webhook for a repository."""
    url = f"{handler.base_url}/repos/{owner}/{repo}/hooks/{hook_id}"
    try:
        response = await handler.client.delete(url, headers=handler.headers)
        if response.status_code == 204:
            logger.info(f"Webhook deleted for {owner}/{repo}")
        else:
            logger.error(f"Failed to delete webhook for {owner}/{repo}: {response.text}")
    except Exception as e:
        logger.error(f"Error deleting webhook for {owner}/{repo}: {e}")