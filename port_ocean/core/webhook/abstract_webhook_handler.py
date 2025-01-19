from abc import ABC, abstractmethod
from typing import Any, Dict, TypeAlias
from fastapi import Request

# Use TypeAlias instead of 'type' for Python <3.12 compatibility
EventPayload: TypeAlias = Dict[str, Any]


class AbstractWebhookHandler(ABC):
    """Abstract base class for webhook handlers."""

    def __init__(self) -> None:
        self.retry_count = 3
        self.circuit_breaker_failure_threshold = 5
        self.failure_count = 0
        self.circuit_open = False
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

    async def process_request(self, request: Request) -> None:
        """Main method to process a webhook request."""
        if self.circuit_open:
            raise ValueError("Circuit is open. Rejecting requests temporarily.")

        try:
            # Authentication
            if not self.authenticate(request):
                raise ValueError("Authentication failed")

            # Rate Limiting
            if not self.rate_limit(request):
                raise ValueError("Rate limit exceeded")

            # Parse Payload
            payload = await request.json()

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
            if not self.retry_logic(request):
                raise e

    @abstractmethod
    def authenticate(self, request: Request) -> bool:
        """Authenticate the request."""
        pass

    @abstractmethod
    def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the payload structure and content."""
        pass

    @abstractmethod
    def rate_limit(self, request: Request) -> bool:
        """Apply rate limiting."""
        pass

    @abstractmethod
    def collect_metrics(self, success: bool) -> None:
        """Collect metrics for the request."""
        pass

    @abstractmethod
    def retry_logic(self, request: Request) -> bool:
        """Implement retry mechanisms."""
        pass

    @abstractmethod
    async def handle_event(self, payload: EventPayload) -> None:
        """Process the event."""
        pass
