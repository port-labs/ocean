from typing import Any, Dict
from loguru import logger

from ..base import HookHandler

__all__ = ['TeamHandler']

class TeamHandler(HookHandler):
    """Handler for GitHub team events."""
    github_events = ["team", "team_add", "membership"]
    
    async def handle(self, event: str, body: Dict[str, Any]) -> None:
        try:
            team = body.get("team", {})
            if not team:
                logger.warning("No team data in event")
                return

            # The team data from webhook is already enriched with members and permissions
            # We just need to register it
            await self.register_resource("team", [team])
            
            # Handle team_add event which includes repository data
            if event == "team_add":
                repository = body.get("repository")
                if repository:
                    await self.register_resource("team_repository", [{
                        "team": team,
                        "repository": repository
                    }])
            
            # Handle membership event which includes the user
            elif event == "membership":
                user = body.get("user")
                if user:
                    await self.register_resource("team_member", [{
                        "team": team,
                        "user": user,
                        "action": body.get("action")
                    }])
            
        except Exception as e:
            logger.error(f"Error handling team event: {e}")
            raise
