import asyncio
import hmac
from abc import ABC, abstractmethod
from hashlib import sha256
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
        
    def verify_signature(self, signature: Optional[str], body: bytes) -> bool:
        """Verify the webhook signature.
        
        Args:
            signature: The X-Hub-Signature-256 header value
            body: Raw request body bytes
            
        Returns:
            bool: True if signature is valid or no secret configured
        """
        webhook_secret = ocean.integration_config.get("github_webhook_secret")
        if not webhook_secret:
            logger.warning("No webhook secret configured - skipping signature verification")
            return True
            
        if not signature:
            logger.error("No signature provided in webhook request")
            return False
            
        if not signature.startswith('sha256='):
            logger.error(f"Invalid signature format: {signature}")
            return False
            
        # Get the signature hex digest
        sig = signature.removeprefix('sha256=')
        
        # Calculate expected signature
        mac = hmac.new(webhook_secret.encode(), body, sha256)
        expected_sig = mac.hexdigest()
        
        # Compare signatures using hmac.compare_digest to prevent timing attacks
        return hmac.compare_digest(sig, expected_sig)

    @abstractmethod
    async def handle(self, event: str, body: Dict[str, Any], raw_body: bytes, signature: Optional[str] = None) -> None:
        """Handle a GitHub webhook event.
        
        Args:
            event: The GitHub event type (e.g. 'push', 'issues', 'pull_request')
            body: The webhook payload
            raw_body: Raw request body bytes for signature verification
            signature: The X-Hub-Signature-256 header value
        """
        if not self.verify_signature(signature, raw_body):
            raise ValueError("Invalid webhook signature")

    async def handle_with_retry(self, event: str, body: Dict[str, Any], raw_body: bytes, signature: Optional[str] = None, max_retries: int = 3) -> None:
        """Handle a webhook event with retries on failure.

        Args:
            event: The GitHub event type
            body: The webhook payload
            max_retries: Maximum number of retry attempts
        """
        for attempt in range(max_retries):
            try:
                await self.handle(event, body, raw_body, signature)
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
