from typing import Any, Dict, Optional
from loguru import logger

from .base import HookHandler
from constants import ObjectKind

class IssueHandler(HookHandler):
    """Handler for GitHub issue events."""
    github_events = ["issues"]

    async def handle(self, event: str, body: dict[str, Any], raw_body: bytes, signature: Optional[str] = None) -> None:
        await super().handle(event, body, raw_body, signature)
        
        action = body.get("action")
        issue = body.get("issue", {})
        repo = body.get("repository", {})
        logger.info(f"Processing issue {action}: {issue.get('title')}")
        
        if not self.client:
            raise ValueError("GitHub client not configured")
            
        # Fetch full issue data
        issue_number = issue.get("number")
        repo_name = repo.get("name")
        if not issue_number or not repo_name:
            raise ValueError("Missing issue number or repo name in webhook payload")
            
        issue_data = await self.client.get_issue(repo_name, issue_number)
        await self.register_resource(ObjectKind.ISSUE, [issue_data])

class PushHandler(HookHandler):
    """Handler for GitHub push events."""
    github_events = ["push"]

    async def handle(self, event: str, body: dict[str, Any], raw_body: bytes, signature: Optional[str] = None) -> None:
        await super().handle(event, body, raw_body, signature)
        
        repo = body.get("repository", {})
        logger.info(f"Processing push to: {repo.get('full_name')}")
        
        if not self.client:
            raise ValueError("GitHub client not configured")
            
        # Fetch updated repository data
        repo_name = repo.get("name")
        if not repo_name:
            raise ValueError("Missing repository name in webhook payload")
            
        repo_data = await self.client.get_repository(repo_name)
        await self.register_resource(ObjectKind.REPOSITORY, [repo_data])

class PullRequestHandler(HookHandler):
    """Handler for GitHub pull request events."""
    github_events = ["pull_request"]

    async def handle(self, event: str, body: dict[str, Any], raw_body: bytes, signature: Optional[str] = None) -> None:
        await super().handle(event, body, raw_body, signature)
        
        pr = body.get("pull_request", {})
        repo = body.get("repository", {})
        logger.info(f"Processing PR: {pr.get('title')}")
        
        if not self.client:
            raise ValueError("GitHub client not configured")
            
        # Fetch full PR data
        pr_number = pr.get("number")
        repo_name = repo.get("name")
        if not pr_number or not repo_name:
            raise ValueError("Missing PR number or repo name in webhook payload")
            
        pr_data = await self.client.get_pull_request(repo_name, pr_number)
        await self.register_resource(ObjectKind.PULLREQUEST, [pr_data])
