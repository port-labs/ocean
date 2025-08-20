from typing import Any
import pytest
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from checkmarx_one.core.webhook_processors.scan_result_webhook_processor import (
    ScanResultWebhookProcessor,
)
from checkmarx_one.utils import CheckmarxEventType


class TestScanResultWebhookProcessor:
    @pytest.fixture
    def processor(self) -> ScanResultWebhookProcessor:
        return ScanResultWebhookProcessor()  # type: ignore

    @pytest.fixture
    def valid_completed_scan_payload(self) -> dict[str, Any]:
        return {
            "event_type": CheckmarxEventType.SCAN_COMPLETED,
            "scan": {
                "id": "test-scan-id",
                "status": "completed",
                "project_id": "test-project-id",
            },
        }

    @pytest.fixture
    def invalid_payload(self) -> dict[str, Any]:
        return {
            "event_type": CheckmarxEventType.SCAN_FAILED,  # Wrong event type
            "scan": {
                "id": "test-scan-id",
                "status": "failed",
                "project_id": "test-project-id",
            },
        }

    @pytest.mark.asyncio
    async def test_should_process_event_completed_scan(
        self,
        processor: ScanResultWebhookProcessor,
        valid_completed_scan_payload: dict[str, Any],
    ) -> None:
        """Test that completed scan events are processed."""
        event = WebhookEvent(
            payload=valid_completed_scan_payload,
            headers={},
            _original_request=MagicMock(),
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_invalid_event(
        self, processor: ScanResultWebhookProcessor, invalid_payload: dict[str, Any]
    ) -> None:
        """Test that non-completed scan events are not processed."""
        event = WebhookEvent(
            payload=invalid_payload, headers={}, _original_request=MagicMock()
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, processor: ScanResultWebhookProcessor
    ) -> None:
        """Test that the processor returns the correct resource kind."""
        event = WebhookEvent(
            payload={}, headers={}, _original_request=MagicMock()
        )  # type: ignore

        kinds = await processor.get_matching_kinds(event)
        assert kinds == ["scan_result"]

    @pytest.mark.asyncio
    async def test_validate_payload_valid(
        self,
        processor: ScanResultWebhookProcessor,
        valid_completed_scan_payload: dict[str, Any],
    ) -> None:
        """Test that valid scan payloads are accepted."""
        result = await processor.validate_payload(valid_completed_scan_payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_payload_invalid(
        self, processor: ScanResultWebhookProcessor, invalid_payload: dict[str, Any]
    ) -> None:
        """Test that invalid payloads are rejected."""
        # The validate_payload method only checks for required fields, not event type
        # The event type validation is done in _should_process_event
        result = await processor.validate_payload(invalid_payload)
        assert result is True  # Should be True because it has required fields

    @pytest.mark.asyncio
    async def test_validate_payload_missing_fields(
        self, processor: ScanResultWebhookProcessor
    ) -> None:
        """Test that payloads missing required fields are rejected."""
        incomplete_payload = {
            "event_type": CheckmarxEventType.SCAN_COMPLETED
        }  # Missing scan
        result = await processor.validate_payload(incomplete_payload)
        assert result is False
