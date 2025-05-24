from typing import Any, Dict
from loguru import logger

from ..base import HookHandler

class ResourceHandler(HookHandler):
    """Base class for GitHub resource handlers."""
    
    async def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a resource with additional data.
        
        Args:
            resource: The resource to enrich
            
        Returns:
            The enriched resource
        """
        return resource

class RepositoryHandler(ResourceHandler):
    """Base handler for repository-related events."""
    
    async def handle(self, event: str, body: Dict[str, Any]) -> None:
        repo = body.get("repository", {})
        if not repo:
            logger.warning(f"No repository data in {event} event")
            return
            
        try:
            enriched_repo = await self.enrich_resource(repo)
            await self.register_resource("repository", [enriched_repo])
            await self._handle_repository_event(event, body, enriched_repo)
        except Exception as e:
            logger.error(f"Error handling repository event {event}: {e}")
            raise

    async def _handle_repository_event(self, event: str, body: Dict[str, Any], repo: Dict[str, Any]) -> None:
        """Handle repository-specific event logic.
        
        Args:
            event: The event type
            body: The full event payload
            repo: The enriched repository data
        """
        pass

    async def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich repository data with additional information.
        
        Args:
            resource: Repository data to enrich
            
        Returns:
            Enriched repository data
        """
        if not self.client:
            return resource
            
        try:
            repo_name = resource.get("name")
            if repo_name:
                details = await self.client.get_repository_details(repo_name)
                resource.update(details)
        except Exception as e:
            logger.warning(f"Error enriching repository data: {e}")
            
        return resource
