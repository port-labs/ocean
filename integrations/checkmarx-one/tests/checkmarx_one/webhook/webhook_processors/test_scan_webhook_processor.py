from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.scan_webhook_processor import (
    ScanWebhookProcessor,
)
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from integration import CheckmarxOneScanResourcesConfig, CheckmarxOneScanSelector


@pytest.fixture
def scan_resource_config() -> CheckmarxOneScanResourcesConfig:
    return CheckmarxOneScanResourcesConfig(
        kind="scan",
        selector=CheckmarxOneScanSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"checkmarxScan"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def scan_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ScanWebhookProcessor:
    return ScanWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestScanWebhookProcessor:

    @pytest.mark.parametrize(
        "checkmarx_event,result",
        [
            (CheckmarxEventType.SCAN_COMPLETED, True),
            (CheckmarxEventType.SCAN_FAILED, True),
            (CheckmarxEventType.SCAN_PARTIAL, True),
            ("invalid_event", False),
        ],
    )
    async def test_should_process_event(
        self,
        scan_webhook_processor: ScanWebhookProcessor,
        checkmarx_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-cx-webhook-event": checkmarx_event},
        )
        event._original_request = mock_request

        assert await scan_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, scan_webhook_processor: ScanWebhookProcessor
    ) -> None:
        kinds = await scan_webhook_processor.get_matching_kinds(
            scan_webhook_processor.event
        )
        assert ObjectKind.SCAN in kinds

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "scanId": "scan-123",
                    "projectId": "project-456",
                },
                True,
            ),
            (
                {
                    "scanId": "scan-789",
                    "projectId": "project-101",
                    "additionalField": "value",
                },
                True,
            ),
            (
                {
                    "projectId": "project-456",
                },  # missing scanId
                False,
            ),
            (
                {
                    "scanId": "scan-123",
                },  # missing projectId
                False,
            ),
            (
                {},  # empty payload
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        scan_webhook_processor: ScanWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await scan_webhook_processor.validate_payload(payload)
        assert result is expected

    async def test_handle_event_success(
        self,
        scan_webhook_processor: ScanWebhookProcessor,
        scan_resource_config: CheckmarxOneScanResourcesConfig,
    ) -> None:
        """Test handling a scan event successfully."""
        scan_data = {
            "id": "scan-123",
            "project_id": "project-456",
            "status": "Completed",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T01:00:00Z",
            "branch": "main",
            "scan_type": "sast",
        }

        payload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the scan exporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = scan_data

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.scan_webhook_processor.create_scan_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await scan_webhook_processor.handle_event(
                payload, scan_resource_config
            )

            # Verify exporter was called with correct parameters
            mock_exporter.get_resource.assert_called_once()
            call_args = mock_exporter.get_resource.call_args[0][0]
            assert call_args["scan_id"] == "scan-123"

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == scan_data

    async def test_handle_event_exporter_error(
        self,
        scan_webhook_processor: ScanWebhookProcessor,
        scan_resource_config: CheckmarxOneScanResourcesConfig,
    ) -> None:
        """Test handling when the exporter raises an error."""
        payload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the scan exporter to raise an exception
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.side_effect = Exception("API Error")

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.scan_webhook_processor.create_scan_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await scan_webhook_processor.handle_event(payload, scan_resource_config)

    async def test_authenticate_returns_true(
        self, scan_webhook_processor: ScanWebhookProcessor
    ) -> None:
        """Test that authenticate method returns True."""
        payload = EventPayload({"scanId": "scan-123", "projectId": "project-456"})
        headers = EventHeaders(
            {"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED}
        )

        result = await scan_webhook_processor.authenticate(payload, headers)
        assert result is True

    async def test_should_process_event_with_valid_request(
        self, scan_webhook_processor: ScanWebhookProcessor
    ) -> None:
        """Test should_process_event with valid request and signature."""
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = mock_request

        # Mock _verify_webhook_signature to return True
        with patch.object(
            scan_webhook_processor, "_verify_webhook_signature", return_value=True
        ):
            result = await scan_webhook_processor.should_process_event(event)
            assert result is True

    async def test_should_process_event_without_request(
        self, scan_webhook_processor: ScanWebhookProcessor
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = None

        result = await scan_webhook_processor.should_process_event(event)
        assert result is False
