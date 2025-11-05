from typing import Dict, Any, List
from abc import ABC, abstractmethod
import time
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.context.ocean import ocean

from harbor.clients.harbor_client import HarborClient
from harbor.helpers.webhook_utils import validate_webhook_signature, extract_resource_info
from harbor.helpers.metrics import WebhookMetrics


class BaseHarborWebhookProcessor(AbstractWebhookProcessor, ABC):
    """Base class for Harbor webhook processors."""
    
    def __init__(self):
        super().__init__()
        self.client = self._create_harbor_client()
        
    def _create_harbor_client(self) -> HarborClient:
        """Create Harbor client from configuration."""
        config = ocean.integration_config
        return HarborClient(
            base_url=config["harbor_url"],
            username=config["username"],
            password=config["password"],
            max_concurrent_requests=config.get("max_concurrent_requests", 10),
            request_timeout=config.get("request_timeout", 30),
            rate_limit_delay=config.get("rate_limit_delay", 0.1),
            verify_ssl=config.get("verify_ssl", True)
        )
        
    async def process(self, webhook_event: WebhookEvent) -> List[Dict[str, Any]]:
        """Process Harbor webhook event."""
        start_time = time.time()
        event_type = None
        
        try:
            # Parse event data first to get event type for logging
            event_data = webhook_event.body_json
            resource_info = extract_resource_info(event_data)
            event_type = resource_info['event_type']
            
            WebhookMetrics.log_webhook_received(
                event_type, 
                resource_info.get('project_name'),
                resource_info.get('repository_name')
            )
            
            # Validate webhook signature
            webhook_secret = ocean.integration_config.get("webhook_secret")
            signature = webhook_event.headers.get("x-harbor-signature", "")
            
            is_valid = validate_webhook_signature(webhook_event.body, signature, webhook_secret)
            WebhookMetrics.log_signature_validation(is_valid, event_type)
            
            if not is_valid:
                WebhookMetrics.log_webhook_error(event_type, "Signature validation failed")
                return []
            
            logger.info(f"Processing Harbor webhook event: {event_type}")
            logger.debug(f"Resource info: {resource_info}")
            
            # Process the specific event
            result = await self._process_event(event_data, resource_info)
            
            processing_time = (time.time() - start_time) * 1000
            WebhookMetrics.log_webhook_processed(event_type, len(result), processing_time)
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            WebhookMetrics.log_webhook_error(event_type or "unknown", error_msg)
            logger.error(f"Error processing Harbor webhook: {error_msg}")
            return []
            
    @abstractmethod
    async def _process_event(self, event_data: Dict[str, Any], resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process the specific Harbor event. Must be implemented by subclasses."""
        pass