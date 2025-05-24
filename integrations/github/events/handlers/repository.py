from typing import Any, Dict
from loguru import logger

from .base_resource import RepositoryHandler

__all__ = ['RepositoryEventHandler']

class RepositoryEventHandler(RepositoryHandler):
    """Handler for GitHub repository events."""
    github_events = [
        "repository",
        "repository_import",
        "repository_vulnerability_alert",
        "star",
        "fork"
    ]
    
    async def _handle_repository_event(self, event: str, body: Dict[str, Any], repo: Dict[str, Any]) -> None:
        try:
            enriched_repo = await self.enrich_resource(repo)
            await self.register_resource("repository", [enriched_repo])
            
            # Handle specific repository sub-events
            if event == "repository_vulnerability_alert":
                await self._handle_vulnerability_alert(body)
            elif event == "star":
                await self._handle_star_event(body)
            elif event == "fork":
                await self._handle_fork_event(body)
                
        except Exception as e:
            logger.error(f"Error handling repository event: {e}")
            raise
            
    async def _handle_vulnerability_alert(self, body: Dict[str, Any]) -> None:
        """Handle repository vulnerability alert events."""
        alert = body.get("alert", {})
        if alert:
            await self.register_resource("vulnerability_alert", [alert])
            
    async def _handle_star_event(self, body: Dict[str, Any]) -> None:
        """Handle repository star events."""
        if self.client:
            try:
                repo_name = body.get("repository", {}).get("full_name")
                if repo_name:
                    stars = await self.client.get_repository_stars(repo_name)
                    await self.register_resource("repository_stars", [stars])
            except Exception as e:
                logger.warning(f"Error handling star event: {e}")
                
    async def _handle_fork_event(self, body: Dict[str, Any]) -> None:
        """Handle repository fork events."""
        fork = body.get("forkee", {})
        if fork:
            await self.register_resource("repository_fork", [fork])
