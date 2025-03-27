import pytest
import json
import hashlib
import hmac
from unittest.mock import MagicMock, patch
from typing import Any
from fastapi import Request
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient

# Patch the module before importing the class
with patch("initialize_client.init_webhook_client") as mock_init_client:
    from bitbucket_cloud.webhook_processors.processors._bitbucket_abstract_webhook_processor import (
        _BitbucketAbstractWebhookProcessor,
    )


# Create a concrete implementation for testing the abstract class
class ConcreteWebhookProcessor(_BitbucketAbstractWebhookProcessor):
    """Concrete implementation of the abstract webhook processor for testing."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Test implementation of the abstract method."""
        # Process events with a specific test header
        return event.headers.get("x-test-event") == "process"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Test implementation of the abstract method."""
        return ["test_kind"]

    async def handle_event(self, payload: dict[str, Any], resource_config: Any) -> Any:
        """Test implementation of the abstract method."""
        return {"test": "result"}

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        """Test implementation of the abstract method."""
        return True

    # Add a property to fix the issue with self.secret in _verify_webhook_signature
    @property
    def secret(self) -> str:
        """Return the secret from the webhook client."""
        return self._webhook_client.secret if self._webhook_client.secret else ""


# Create a mock request for testing
def create_mock_request(body: bytes, headers: dict[str, str]) -> Request:
    """Create a mock FastAPI Request object for testing."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = headers

    # Create a mock body() coroutine that returns the bytes
    async def mock_body() -> bytes:
        return body

    mock_request.body = mock_body
    return mock_request


def compute_signature(secret: str, payload: dict[str, Any]) -> str:
    """Compute the HMAC-SHA256 signature in the expected format."""
    payload_bytes = json.dumps(payload).encode("utf-8")
    return (
        "sha256="
        + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    )


@pytest.fixture
def event() -> WebhookEvent:
    """Fixture to create a basic webhook event."""
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def webhook_processor(
    event: WebhookEvent, webhook_client_mock: BitbucketWebhookClient
) -> ConcreteWebhookProcessor:
    """Create a concrete webhook processor with a mocked client."""
    processor = ConcreteWebhookProcessor(event)
    processor._webhook_client = webhook_client_mock
    return processor


class TestBitbucketAbstractWebhookProcessor:
    """Tests for the _BitbucketAbstractWebhookProcessor class."""

    @pytest.mark.asyncio
    async def test_authenticate(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test the authenticate method."""
        result = await webhook_processor.authenticate({}, {})
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_secret(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test signature verification when no secret is configured."""
        # Mock the webhook client with no secret
        webhook_processor._webhook_client.secret = None

        mock_request = MagicMock(spec=Request)

        result = await webhook_processor._verify_webhook_signature(mock_request)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_header(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test signature verification when no signature header is provided."""
        # Mock the webhook client with a secret
        webhook_processor._webhook_client.secret = "test-secret"

        mock_request = create_mock_request(b"{}", {})

        result = await webhook_processor._verify_webhook_signature(mock_request)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_valid(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test signature verification with a valid signature."""
        # Set up the test
        secret = "test-secret"
        webhook_processor._webhook_client.secret = secret

        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")

        valid_signature = compute_signature(secret, payload)
        headers = {"x-hub-signature": valid_signature}

        mock_request = create_mock_request(payload_bytes, headers)

        result = await webhook_processor._verify_webhook_signature(mock_request)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test signature verification with an invalid signature."""
        # Set up the test
        secret = "test-secret"
        webhook_processor._webhook_client.secret = secret

        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")

        invalid_signature = "sha256=invalid"
        headers = {"x-hub-signature": invalid_signature}

        mock_request = create_mock_request(payload_bytes, headers)

        result = await webhook_processor._verify_webhook_signature(mock_request)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_no_request(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test should_process_event when no original request is available."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-test-event": "process"},
            payload={},
        )
        # Ensure there's no original request
        event._original_request = None

        result = await webhook_processor.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_implementation_returns_false(
        self, webhook_processor: ConcreteWebhookProcessor
    ) -> None:
        """Test should_process_event when the implementation returns False."""
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        headers = {"x-test-event": "do-not-process"}

        mock_request = create_mock_request(payload_bytes, headers)

        event = WebhookEvent(
            trace_id="test-trace-id",
            headers=headers,
            payload=payload,
        )
        event._original_request = mock_request

        # Update the webhook processor with this event
        webhook_processor.event = event

        result = await webhook_processor.should_process_event(event)
        assert result is False
