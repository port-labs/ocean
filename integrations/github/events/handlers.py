from typing import Any
from loguru import logger

from .base import HookHandler

class IssueHandler(HookHandler):
    """Handler for GitHub issue events."""
    github_events = ["issues"]

    async def handle(self, event: str, body: dict[str, Any]) -> None:
        action = body.get("action")
        issue = body.get("issue", {})
        logger.info(f"Issue {action}: {issue.get('title')}")

class PushHandler(HookHandler):
    """Handler for GitHub push events."""
    github_events = ["push"]

    async def handle(self, event: str, body: dict[str, Any]) -> None:
        repo = body.get("repository", {})
        logger.info(f"Push to: {repo.get('full_name')}")

class PullRequestHandler(HookHandler):
    """Handler for GitHub pull request events."""
    github_events = ["pull_request"]

    async def handle(self, event: str, body: dict[str, Any]) -> None:
        pr = body.get("pull_request", {})
        logger.info(f"PR: {pr.get('title')}")
