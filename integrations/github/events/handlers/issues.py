from typing import Any, Dict
from loguru import logger

from .base_resource import RepositoryHandler

__all__ = ['IssueHandler']

class IssueHandler(RepositoryHandler):
    """Handler for issue events."""
    github_events = ["issues"]
    
    async def _handle_repository_event(self, event: str, body: Dict[str, Any], repo: Dict[str, Any]) -> None:
        issue = body.get("issue", {})
        if not issue:
            logger.warning("No issue data in event")
            return
            
        try:
            enriched_issue = await self._enrich_issue(issue)
            await self.register_resource("issue", [enriched_issue])
        except Exception as e:
            logger.error(f"Error handling issue: {e}")
            raise
            
    async def _enrich_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich issue data with additional information."""
        if not self.client:
            return issue
            
        try:
            issue_number = issue.get("number")
            repo_name = issue.get("repository", {}).get("full_name")
            if issue_number and repo_name:
                details = await self.client.get_issue_details(repo_name, issue_number)
                issue.update(details)
        except Exception as e:
            logger.warning(f"Error enriching issue data: {e}")
            
        return issue
