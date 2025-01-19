from abc import ABC, abstractmethod
from typing import Dict

from .webhook_event import WebhookEvent, EventPayload


class AbstractWebhookHandler(ABC):
    """Abstract base class for webhook handlers."""

    def __init__(self, event: WebhookEvent) -> None:
        self.retry_count = 3
        self.circuit_breaker_failure_threshold = 5
        self.failure_count = 0
        self.circuit_open = False
        self.event = event
        self.initialize()

    def initialize(self) -> None:
        """Initialize resources (e.g., API clients)."""
        pass

    def validate_webhook_setup(self) -> None:
        """Validate third-party webhook configurations."""
        pass

    def teardown(self) -> None:
        """Clean up resources when no longer needed."""
        pass

    async def process_request(self) -> None:
        """Main method to process a webhook request."""
        if self.circuit_open:
            raise ValueError("Circuit is open. Rejecting requests temporarily.")

        try:
            payload = self.event.payload
            headers = self.event.headers
            # Authentication
            if not self.authenticate(payload, headers):
                raise ValueError("Authentication failed")

            # Payload Validation
            if not self.validate_payload(payload):
                raise ValueError("Invalid payload")

            # Handle Event
            await self.handle_event(payload)

            # Metrics Collection
            self.collect_metrics(success=True)
            self.failure_count = 0  # Reset failure count on success

        except Exception as e:
            self.collect_metrics(success=False)
            self.failure_count += 1
            if self.failure_count >= self.circuit_breaker_failure_threshold:
                self.circuit_open = True
            if not self.retry_logic():
                raise e

    @abstractmethod
    def authenticate(self, payload: EventPayload, headers: Dict[str, str]) -> bool:
        """Authenticate the request."""
        pass

    @abstractmethod
    def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the payload structure and content."""
        pass

    @abstractmethod
    def collect_metrics(self, success: bool) -> None:
        """Collect metrics for the request."""
        pass

    @abstractmethod
    def retry_logic(self) -> bool:
        """Implement retry mechanisms."""
        pass

    @abstractmethod
    async def handle_event(self, payload: EventPayload) -> None:
        """Process the event."""
        pass
