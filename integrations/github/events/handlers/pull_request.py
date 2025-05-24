from typing import Any, Dict
from loguru import logger

from .base_resource import RepositoryHandler

__all__ = ['PullRequestHandler']

class PullRequestHandler(RepositoryHandler):
    """Handler for pull request events."""
    github_events = ["pull_request"]
    
    async def _handle_repository_event(self, event: str, body: Dict[str, Any], repo: Dict[str, Any]) -> None:
        pr = body.get("pull_request", {})
        if not pr:
            logger.warning("No pull request data in event")
            return
            
        try:
            enriched_pr = await self._enrich_pull_request(pr)
            await self.register_resource("pull_request", [enriched_pr])
        except Exception as e:
            logger.error(f"Error handling pull request: {e}")
            raise
            
    async def _enrich_pull_request(self, pr: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich pull request data with additional information."""
        if not self.client:
            return pr
            
        try:
            # Add additional PR data like:
            # - Review status
            # - CI status
            # - Related issues
            pr_number = pr.get("number")
            repo_name = pr.get("base", {}).get("repo", {}).get("full_name")
            if pr_number and repo_name:
                details = await self.client.get_pull_request_details(repo_name, pr_number)
                pr.update(details)
        except Exception as e:
            logger.warning(f"Error enriching pull request data: {e}")
            
        return pr
