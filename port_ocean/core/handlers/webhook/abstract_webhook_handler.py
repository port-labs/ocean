from abc import ABC, abstractmethod
from typing import Dict, Optional
import asyncio
from loguru import logger

from .webhook_event import WebhookEvent, EventPayload


class RetryableError(Exception):
    """Base exception class for errors that should trigger a retry."""

    pass


class AbstractWebhookHandler(ABC):
    """Abstract base class for webhook handlers."""

    # Default retry configuration
    max_retries: int = 3
    initial_retry_delay: float = 1.0  # seconds
    max_retry_delay: float = 30.0  # seconds
    exponential_base: float = 2.0

    def __init__(self, event: WebhookEvent) -> None:
        self.event = event
        self.retry_count = 0
        self.initialize()

    @property
    def event_kind(self) -> Optional[str]:
        """Extract event type from the webhook payload. Override if needed."""
        return None

    @property
    def resource_id(self) -> Optional[str]:
        """Extract resource identifier from the webhook payload. Override if needed."""
        return None

    async def on_error(self, error: Exception) -> None:
        """Hook to handle errors during processing. Override if needed."""
        logger.error(f"Error processing webhook: {error}")

    def initialize(self) -> None:
        """Initialize resources (e.g., API clients). Override if needed."""
        pass

    def teardown(self) -> None:
        """Clean up resources. Override if needed."""
        pass

    async def cancel(self) -> None:
        """Handle cancellation of the request. Override if needed."""
        pass

    def validate_webhook_setup(self) -> bool:
        """Validate webhook configuration. Override if needed."""
        return True

    def should_retry(self, error: Exception) -> bool:
        """
        Determine if the operation should be retried based on the error.
        Override to customize retry behavior.
        """
        return isinstance(error, RetryableError)

    def calculate_retry_delay(self) -> float:
        """
        Calculate the delay before the next retry using exponential backoff.
        Override to customize backoff strategy.
        """
        delay = min(
            self.initial_retry_delay * (self.exponential_base**self.retry_count),
            self.max_retry_delay,
        )
        return delay

    async def process_request(self) -> None:
        """Main method to process a webhook request with retry logic."""
        if not self.validate_webhook_setup():
            raise ValueError("Invalid webhook setup")

        payload = self.event.payload
        headers = self.event.headers

        if not await self.authenticate(payload, headers):
            raise ValueError("Authentication failed")

        if not await self.validate_payload(payload):
            raise ValueError("Invalid payload")

        while True:
            try:
                await self.handle_event(payload)
                break  # Success, exit retry loop

            except Exception as e:
                if self.should_retry(e) and self.retry_count < self.max_retries:
                    self.retry_count += 1
                    delay = self.calculate_retry_delay()

                    logger.warning(
                        f"Attempt {self.retry_count}/{self.max_retries} failed. "
                        f"Retrying in {delay:.2f} seconds. Error: {str(e)}"
                    )

                    await asyncio.sleep(delay)
                    continue

                await self.on_error(e)
                raise

    @abstractmethod
    async def authenticate(
        self, payload: EventPayload, headers: Dict[str, str]
    ) -> bool:
        """Authenticate the request."""
        pass

    @abstractmethod
    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the payload structure and content."""
        pass

    @abstractmethod
    async def handle_event(self, payload: EventPayload) -> None:
        """Process the event."""
        pass
