from typing import Any, Dict
from loguru import logger

from .base_resource import RepositoryHandler

__all__ = ['WorkflowHandler']

class WorkflowHandler(RepositoryHandler):
    """Handler for GitHub workflow events."""
    github_events = ["workflow_run", "workflow_dispatch", "workflow_job"]
    
    async def _handle_repository_event(self, event: str, body: Dict[str, Any], repo: Dict[str, Any]) -> None:
        try:
            # Handle workflow run events
            if event == "workflow_run":
                workflow_run = body.get("workflow_run", {})
                if workflow_run:
                    await self.register_resource("workflow_run", [workflow_run])
                    
            # Handle workflow job events
            elif event == "workflow_job":
                workflow_job = body.get("workflow_job", {})
                if workflow_job:
                    await self.register_resource("workflow_job", [workflow_job])
                    
            # Handle workflow dispatch events
            elif event == "workflow_dispatch":
                workflow = body.get("workflow", {})
                if workflow:
                    await self.register_resource("workflow", [workflow])
                    
            # Get all workflows for the repository if client is available
            if self.client and repo:
                org_name = repo.get("owner", {}).get("login")
                repo_name = repo.get("name")
                if org_name and repo_name:
                    async for workflows in self.client.get_workflows(org_name, repo_name):
                        await self.register_resource("workflow", workflows)
                        
        except Exception as e:
            logger.error(f"Error handling workflow event: {e}")
            raise
