import pytest
from typing import Any
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from checkmarx_one.core.webhook_processors.scan_webhook_processor import (
    ScanWebhookProcessor,
)


class TestScanWebhookProcessor:
    @pytest.fixture
    def processor(self) -> ScanWebhookProcessor:
        return ScanWebhookProcessor()  # type: ignore

    @pytest.fixture
    def valid_completed_scan_payload(self) -> dict[str, Any]:
        return {
            "event_type": "Completed Scan",
            "scan": {
                "id": "test-scan-id",
                "status": "completed",
                "project_id": "test-project-id",
            },
        }

    @pytest.fixture
    def valid_failed_scan_payload(self) -> dict[str, Any]:
        return {
            "event_type": "Failed Scan",
            "scan": {
                "id": "test-scan-id",
                "status": "failed",
                "project_id": "test-project-id",
            },
        }

    @pytest.fixture
    def valid_partial_scan_payload(self) -> dict[str, Any]:
        return {
            "event_type": "Partial Scan",
            "scan": {
                "id": "test-scan-id",
                "status": "partial",
                "project_id": "test-project-id",
            },
        }

    @pytest.fixture
    def invalid_payload(self) -> dict[str, Any]:
        return {
            "event_type": "Project Created",  # Wrong event type
            "project": {"id": "test-project-id"},
        }

    @pytest.mark.asyncio
    async def test_should_process_event_completed_scan(
        self,
        processor: ScanWebhookProcessor,
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
    async def test_should_process_event_failed_scan(
        self, processor: ScanWebhookProcessor, valid_failed_scan_payload: dict[str, Any]
    ) -> None:
        """Test that failed scan events are processed."""
        event = WebhookEvent(
            payload=valid_failed_scan_payload, headers={}, _original_request=MagicMock()
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_partial_scan(
        self,
        processor: ScanWebhookProcessor,
        valid_partial_scan_payload: dict[str, Any],
    ) -> None:
        """Test that partial scan events are processed."""
        event = WebhookEvent(
            payload=valid_partial_scan_payload,
            headers={},
            _original_request=MagicMock(),
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_invalid_event(
        self, processor: ScanWebhookProcessor, invalid_payload: dict[str, Any]
    ) -> None:
        """Test that non-scan events are not processed."""
        event = WebhookEvent(
            payload=invalid_payload, headers={}, _original_request=MagicMock()
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor: ScanWebhookProcessor) -> None:
        """Test that the processor returns the correct resource kind."""
        event = WebhookEvent(
            payload={}, headers={}, _original_request=MagicMock()
        )  # type: ignore

        kinds = await processor.get_matching_kinds(event)
        assert kinds == ["scan"]

    @pytest.mark.asyncio
    async def test_validate_payload_valid(
        self,
        processor: ScanWebhookProcessor,
        valid_completed_scan_payload: dict[str, Any],
    ) -> None:
        """Test that valid scan payloads are accepted."""
        result = await processor.validate_payload(valid_completed_scan_payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_payload_invalid(
        self, processor: ScanWebhookProcessor, invalid_payload: dict[str, Any]
    ) -> None:
        """Test that invalid payloads are rejected."""
        result = await processor.validate_payload(invalid_payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_fields(
        self, processor: ScanWebhookProcessor
    ) -> None:
        """Test that payloads missing required fields are rejected."""
        incomplete_payload = {"event_type": "Completed Scan"}  # Missing scan
        result = await processor.validate_payload(incomplete_payload)
        assert result is False
