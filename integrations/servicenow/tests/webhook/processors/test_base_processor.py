import pytest
from unittest.mock import MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook.processors._base_processor import ServicenowAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class MockServicenowProcessor(ServicenowAbstractWebhookProcessor):
    """Mock concrete implementation of ServicenowAbstractWebhookProcessor for testing."""

    def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("process_me", False)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["mock_kind"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )


@pytest.fixture
def base_processor(mock_webhook_event: WebhookEvent) -> MockServicenowProcessor:
    """Fixture for the mock base processor."""
    return MockServicenowProcessor(event=mock_webhook_event)


def _mock_ocean_config(webhook_secret: str | None = None) -> MagicMock:
    mock = MagicMock()
    config = {}
    if webhook_secret is not None:
        config["webhook_secret"] = webhook_secret
    mock.integration_config = config
    return mock


@pytest.mark.asyncio
class TestServicenowAbstractWebhookProcessor:
    """Test suite for ServicenowAbstractWebhookProcessor."""

    async def test_authenticate_no_secret_configured(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        with patch("webhook.processors._base_processor.ocean", _mock_ocean_config()):
            result = await base_processor.authenticate({}, {})
            assert result is True

    async def test_authenticate_matching_secret(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        with patch(
            "webhook.processors._base_processor.ocean",
            _mock_ocean_config("my-secret"),
        ):
            result = await base_processor.authenticate(
                {}, {"authorization": "my-secret"}
            )
            assert result is True

    async def test_authenticate_missing_header(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        with patch(
            "webhook.processors._base_processor.ocean",
            _mock_ocean_config("my-secret"),
        ):
            result = await base_processor.authenticate({}, {})
            assert result is False

    async def test_authenticate_mismatching_secret(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        with patch(
            "webhook.processors._base_processor.ocean",
            _mock_ocean_config("my-secret"),
        ):
            result = await base_processor.authenticate(
                {}, {"authorization": "wrong-secret"}
            )
            assert result is False

    async def test_validate_payload_with_sys_id(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        """Test validate_payload returns True when sys_id is present."""
        payload = {"sys_id": "test_id", "other": "data"}
        result = await base_processor.validate_payload(payload)
        assert result is True

    async def test_validate_payload_missing_sys_id(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        """Test validate_payload returns False when sys_id is missing."""
        payload = {"not_sys_id": "test_id"}
        result = await base_processor.validate_payload(payload)
        assert result is False

    async def test_should_process_event_valid(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        """Test should_process_event returns True for valid ServiceNow events."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"process_me": True}

        result = await base_processor.should_process_event(mock_event)
        assert result is True

    async def test_should_process_event_not_original_request(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        """Test should_process_event returns False if not an original request."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = False
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"process_me": True}

        result = await base_processor.should_process_event(mock_event)
        assert result is False

    async def test_should_process_event_missing_header(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        """Test should_process_event returns False if ServiceNow header is missing."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {}
        mock_event.payload = {"process_me": True}

        result = await base_processor.should_process_event(mock_event)
        assert result is False

    async def test_should_process_event_child_refusal(
        self, base_processor: MockServicenowProcessor
    ) -> None:
        """Test should_process_event returns False if the child's _should_process_event returns False."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"process_me": False}

        result = await base_processor.should_process_event(mock_event)
        assert result is False
