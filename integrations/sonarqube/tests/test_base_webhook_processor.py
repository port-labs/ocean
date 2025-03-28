import pytest
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock
from webhook_processors.base_webhook_processor import BaseSonarQubeWebhookProcessor
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
    EventPayload,
)
from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any, Dict, List, Optional


class _TestableBaseProcessor(BaseSonarQubeWebhookProcessor):
    def __init__(self) -> None:
        mock_event = self._create_mock_event()
        super().__init__(mock_event)

    def _create_mock_event(self) -> WebhookEvent:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {}
        mock_event.headers = {}
        mock_event._original_request = MagicMock()
        mock_event._original_request.body = AsyncMock(return_value=b"")
        return mock_event

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return [ObjectKind.PROJECTS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


class TestBaseWebhookProcessor:
    @pytest.fixture
    def processor(self) -> _TestableBaseProcessor:
        return _TestableBaseProcessor()

    def _create_test_event(
        self,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        body: bytes = b"",
    ) -> WebhookEvent:
        event = MagicMock(spec=WebhookEvent)
        event.payload = payload or {}
        event.headers = headers or {}
        event._original_request = MagicMock()
        event._original_request.body = AsyncMock(return_value=body)
        return event

    @pytest.mark.asyncio
    async def test_should_process_event_with_secret(
        self, mock_ocean_context: Any, processor: _TestableBaseProcessor
    ) -> None:
        ocean.integration_config["webhook_secret"] = "12345"
        body = b"test_body"
        signature = hmac.new("12345".encode("utf-8"), body, hashlib.sha256).hexdigest()

        event = self._create_test_event(
            payload={"project": "test-project"},
            headers={"x-sonar-webhook-hmac-sha256": signature},
            body=body,
        )

        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_no_secret(
        self, mock_ocean_context: Any, processor: _TestableBaseProcessor
    ) -> None:
        ocean.integration_config["webhook_secret"] = None
        event = self._create_test_event(payload={"project": "test-project"})

        result = await processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_payload(
        self, mock_ocean_context: Any, processor: _TestableBaseProcessor
    ) -> None:
        assert await processor.validate_payload({"project": "test"}) is True
        assert await processor.validate_payload({}) is False
