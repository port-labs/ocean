import pytest
import json
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock
from typing import Any
from fastapi import Request
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.launchdarkly_abstract_webhook_processor import (
    _LaunchDarklyAbstractWebhookProcessor,
)
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.ocean import ocean


class MockLaunchDarklyAbstractProcessor(_LaunchDarklyAbstractWebhookProcessor):
    """Test implementation of the LaunchDarkly webhook processor."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Test implementation of the abstract method."""
        # Process events with a specific test header
        return event.headers.get("x-ld-test") == "process"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Test implementation of the abstract method."""
        return ["ld_test_kind"]

    async def handle_event(self, payload: dict[str, Any], resource_config: Any) -> Any:
        """Test implementation of the abstract method."""
        return {"ld_test": "result"}

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        """Test implementation of the abstract method."""
        return True


# Create a mock request for testing
def create_ld_mock_request(body: bytes, headers: dict[str, str]) -> Request:
    """Create a mock FastAPI Request object for testing."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = headers

    # Create a mock body() coroutine that returns the bytes
    async def mock_body() -> bytes:
        return body

    mock_request.body = mock_body
    return mock_request


def generate_ld_signature(secret: str, payload: dict[str, Any]) -> str:
    """Generate the HMAC-SHA256 signature in LaunchDarkly's format."""
    payload_str = json.dumps(payload)
    return hmac.new(
        secret.encode(), payload_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()


@pytest.fixture
def ld_event() -> WebhookEvent:
    """Fixture to create a basic webhook event."""
    return WebhookEvent(trace_id="ld-test-trace", payload={}, headers={})


@pytest.fixture
def ld_processor(ld_event: WebhookEvent) -> MockLaunchDarklyAbstractProcessor:
    """Create a test LaunchDarkly webhook processor."""
    processor = MockLaunchDarklyAbstractProcessor(ld_event)
    return processor


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""
    try:
        mock_ocean_app: MagicMock = MagicMock()
        mock_ocean_app.config.integration.config = {
            "webhook_secret": "test-secret",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestLaunchDarklyAbstractWebhookProcessor:
    """Tests for the _LaunchDarklyAbstractWebhookProcessor class."""

    async def test_verify_webhook_signature_no_secret(
        self, ld_processor: MockLaunchDarklyAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        """Test signature verification when no secret is configured."""
        # Mock the webhook client with no secret

        ocean.integration_config["webhook_secret"] = None

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-LaunchDarkly-Signature": "test-signature"}

        result = await ld_processor._verify_webhook_signature(mock_request)
        assert result is True

    async def test_verify_webhook_signature_no_headers(
        self, ld_processor: MockLaunchDarklyAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        """Test signature verification when no signature headers are provided."""
        # Set up the test

        mock_request = create_ld_mock_request(b"{}", {})

        result = await ld_processor._verify_webhook_signature(mock_request)
        assert result is False

    async def test_verify_webhook_signature_valid(
        self, ld_processor: MockLaunchDarklyAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        """Test signature verification with a valid signature."""
        # Set up the test

        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")

        valid_signature = generate_ld_signature(
            ocean.integration_config["webhook_secret"], payload
        )
        headers = {"x-ld-signature": valid_signature}

        mock_request = create_ld_mock_request(payload_bytes, headers)

        result = await ld_processor._verify_webhook_signature(mock_request)
        assert result is True

    async def test_verify_webhook_signature_invalid(
        self, ld_processor: MockLaunchDarklyAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        """Test signature verification with an invalid signature."""
        # Set up the test
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")

        invalid_signature = "invalid-signature"
        headers = {"x-ld-signature": invalid_signature}

        mock_request = create_ld_mock_request(payload_bytes, headers)

        result = await ld_processor._verify_webhook_signature(mock_request)
        assert result is False

    async def test_should_process_event_no_request(
        self, ld_processor: MockLaunchDarklyAbstractProcessor
    ) -> None:
        """Test should_process_event when no original request is available."""
        event = WebhookEvent(
            trace_id="ld-test-trace",
            headers={"x-ld-signature": "process"},
            payload={},
        )
        # Ensure there's no original request
        event._original_request = None

        result = await ld_processor.should_process_event(event)
        assert result is False

    async def test_should_process_event_implementation_returns_false(
        self, ld_processor: MockLaunchDarklyAbstractProcessor
    ) -> None:
        """Test should_process_event when the implementation returns False."""
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        headers = {"x-ld-signature": "do-not-process"}

        mock_request = create_ld_mock_request(payload_bytes, headers)

        event = WebhookEvent(
            trace_id="ld-test-trace",
            headers=headers,
            payload=payload,
        )
        event._original_request = mock_request

        result = await ld_processor.should_process_event(event)
        assert result is False
