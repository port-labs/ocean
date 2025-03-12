from abc import ABC, abstractmethod
from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.exceptions.webhook_processor import RetryableError

from .webhook_event import (
    WebhookEvent,
    EventPayload,
    EventHeaders,
    WebhookEventRawResults,
)


class AbstractWebhookProcessor(ABC):
    """
    Abstract base class for webhook processors
    Extend this class to implement custom webhook processing logic

    Attributes:
        max_retries: The maximum number of retries before giving up
        initial_retry_delay_seconds: The initial delay before the first retry
        max_retry_delay_seconds: The maximum delay between retries
        exponential_base_seconds: The base for exponential backoff calculations

    Args:
        event: The webhook event to process

    Examples:
        >>> from port_ocean.core.handlers.webhook import AbstractWebhookProcessor
        >>> from port_ocean.core.handlers.webhook import WebhookEvent
        >>> class MyWebhookProcessor(AbstractWebhookProcessor):
        ...     async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        ...         return True
        ...     async def validate_payload(self, payload: EventPayload) -> bool:
        ...         return True
        ...     async def handle_event(self, payload: EventPayload) -> None:
        ...         pass
    """

    max_retries: int = 3
    initial_retry_delay_seconds: float = 1.0
    max_retry_delay_seconds: float = 30.0
    exponential_base_seconds: float = 2.0

    def __init__(self, event: WebhookEvent) -> None:
        self.event = event
        self.retry_count = 0

    async def on_error(self, error: Exception) -> None:
        """Hook to handle errors during processing. Override if needed"""
        delay = self.calculate_retry_delay()

        logger.error(
            f"Attempt {self.retry_count}/{self.max_retries} failed. "
            f"Retrying in {delay:.2f} seconds. Error: {str(error)}"
        )

    async def cancel(self) -> None:
        """Handle cancellation of the request. Override if needed"""
        pass

    def validate_webhook_setup(self) -> bool:
        """Validate webhook configuration. Override if needed"""
        return True

    def should_retry(self, error: Exception) -> bool:
        """
        Determine if the operation should be retried based on the error
        Override to customize retry behavior
        """
        return isinstance(error, RetryableError)

    def calculate_retry_delay(self) -> float:
        """
        Calculate the delay before the next retry using exponential backoff
        Override to customize backoff strategy
        """
        delay = min(
            self.initial_retry_delay_seconds
            * (self.exponential_base_seconds**self.retry_count),
            self.max_retry_delay_seconds,
        )
        return delay

    async def before_processing(self) -> None:
        """Hook to run before processing the event"""
        pass

    async def after_processing(self) -> None:
        """Hook to run after processing the event"""
        pass

    @abstractmethod
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the request."""
        pass

    @abstractmethod
    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the payload structure and content."""
        pass

    @abstractmethod
    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the event."""
        pass

    @abstractmethod
    async def should_process_event(self, event: WebhookEvent) -> bool:
        pass

    @abstractmethod
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        pass
