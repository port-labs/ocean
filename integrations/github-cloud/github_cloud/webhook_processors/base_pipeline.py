from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypeVar, Generic, Type
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
)

T = TypeVar('T')

class BaseEventPipeline(ABC, Generic[T]):
    """Base pipeline class for processing GitHub webhook events."""
    
    def __init__(self):
        self._handlers = {
            'delete': self._handle_delete,
            'upsert': self._handle_upsert,
            'default': self._handle_unknown
        }

    @abstractmethod
    def _extract_event_data(self, payload: EventPayload) -> Optional[T]:
        """Extract and validate event data from the payload."""
        pass

    @abstractmethod
    async def _handle_delete(self, event: T) -> WebhookEventRawResults:
        """Handle resource deletion events."""
        pass

    @abstractmethod
    async def _handle_upsert(self, event: T) -> WebhookEventRawResults:
        """Handle resource creation/update events."""
        pass

    async def _handle_unknown(self, event: T) -> WebhookEventRawResults:
        """Handle unknown or unsupported event types."""
        logger.warning(f"Unsupported event type: {getattr(event, 'action', 'unknown')}")
        return WebhookEventRawResults(
            modified_resources=[],
            removed_resources=[],
        )

    @abstractmethod
    def _determine_handler(self, event: T) -> str:
        """Determine which handler to use based on the event type."""
        pass

    async def process(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        """Process the webhook event through the pipeline."""
        # Extract event data
        event = self._extract_event_data(payload)
        if not event:
            return WebhookEventRawResults(
                modified_resources=[],
                removed_resources=[],
            )

        # Determine and execute appropriate handler
        handler_key = self._determine_handler(event)
        handler = self._handlers[handler_key]
        return await handler(event)

    def _validate_required_fields(self, data: Dict[str, Any], required_fields: list[str]) -> bool:
        """Validate that all required fields are present in the data."""
        return all(field in data and data[field] is not None for field in required_fields)

    def _get_nested_value(self, data: Dict[str, Any], path: list[str], default: Any = None) -> Any:
        """Get a nested value from a dictionary using a path list."""
        current = data
        for key in path:
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
        return current 