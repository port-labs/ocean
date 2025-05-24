import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from loguru import logger

from client.github import GitHubClient
from port_ocean.context.ocean import ocean

class HookHandler(ABC):
    """Base class for GitHub webhook event handlers."""
    # List of GitHub events this handler can process
    github_events: List[str] = []
    
    def __init__(self, client: Optional[GitHubClient] = None) -> None:
        self.client = client

    @abstractmethod
    async def handle(self, event: str, body: Dict[str, Any]) -> None:
        """Handle a GitHub webhook event.
        
        Args:
            event: The GitHub event type (e.g. 'push', 'issues', 'pull_request')
            body: The webhook payload
        """
        pass

    async def handle_with_retry(self, event: str, body: Dict[str, Any], max_retries: int = 3) -> None:
        """Handle a webhook event with retries on failure.

        Args:
            event: The GitHub event type
            body: The webhook payload
            max_retries: Maximum number of retry attempts
        """
        for attempt in range(max_retries):
            try:
                await self.handle(event, body)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed all {max_retries} attempts for event {event}: {e}")
                    raise
                logger.warning(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                await asyncio.sleep(2 ** attempt)

    async def register_resource(self, kind: str, resources: List[Dict[str, Any]]) -> None:
        """Register resources with Ocean.

        Args:
            kind: Resource kind (e.g. 'repository', 'pull_request')
            resources: List of resources to register
        """
        await ocean.register_raw(kind, resources)
