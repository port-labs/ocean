from typing import Any, AsyncIterator, List
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.sca_scan_result_webhook_processor import (
    ScaScanResultWebhookProcessor,
)
from checkmarx_one.utils import ScanResultObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    CheckmarxOneScanResultResourcesConfig,
    CheckmarxOneResultSelector,
)


@pytest.fixture
def sca_scan_result_resource_config() -> CheckmarxOneScanResultResourcesConfig:
    return CheckmarxOneScanResultResourcesConfig(
        kind="sca",
        selector=CheckmarxOneResultSelector(
            query="true",
            severity=["HIGH", "CRITICAL"],
            state=["CONFIRMED", "URGENT"],
            status=["NEW", "RECURRENT"],
            exclude_result_types="NONE",
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"checkmarxScaScanResult"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def sca_scan_result_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ScaScanResultWebhookProcessor:
    return ScaScanResultWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestScaScanResultWebhookProcessor:

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
        sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor,
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

        assert (
            await sca_scan_result_webhook_processor._should_process_event(event)
            is result
        )

    async def test_get_matching_kinds(
        self, sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor
    ) -> None:
        kinds = await sca_scan_result_webhook_processor.get_matching_kinds(
            sca_scan_result_webhook_processor.event
        )
        assert ScanResultObjectKind.SCA in kinds

    async def test_authenticate_always_returns_true(
        self,
        sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor,
    ) -> None:
        """Test that authenticate method always returns True regardless of payload."""
        headers: EventHeaders = {
            "x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED
        }

        # Test with valid payload
        valid_payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }
        result = await sca_scan_result_webhook_processor.authenticate(
            valid_payload, headers
        )
        assert result is True

        # Test with invalid payload (missing fields)
        invalid_payload: EventPayload = {
            "scanId": "scan-123",
        }
        result = await sca_scan_result_webhook_processor.authenticate(
            invalid_payload, headers
        )
        assert result is True

        # Test with empty payload
        empty_payload: EventPayload = {}
        result = await sca_scan_result_webhook_processor.authenticate(
            empty_payload, headers
        )
        assert result is True

    async def test_authenticate_returns_true(
        self, sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor
    ) -> None:
        """Test that authenticate method returns True."""
        payload: EventPayload = {"scanId": "scan-123", "projectId": "project-456"}
        headers: EventHeaders = {
            "x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED
        }

        result = await sca_scan_result_webhook_processor.authenticate(payload, headers)
        assert result is True

    async def test_should_process_event_with_valid_request(
        self, sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor
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
            sca_scan_result_webhook_processor,
            "_verify_webhook_signature",
            return_value=True,
        ):
            result = await sca_scan_result_webhook_processor.should_process_event(event)
            assert result is True

    async def test_should_process_event_without_request(
        self, sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = None

        result = await sca_scan_result_webhook_processor.should_process_event(event)
        assert result is False

    async def test_handle_event_success(
        self,
        sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor,
        sca_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test successful handling of SCA scan result webhook event."""
        sca_scan_result_data = [
            {
                "id": "sca-result-1",
                "scan_id": "scan-123",
                "severity": "HIGH",
                "state": "CONFIRMED",
                "status": "NEW",
                "vulnerability": {
                    "name": "CVE-2023-1234",
                    "description": "Test vulnerability",
                },
                "__scan_id": "scan-123",
            },
            {
                "id": "sca-result-2",
                "scan_id": "scan-123",
                "severity": "CRITICAL",
                "state": "URGENT",
                "status": "RECURRENT",
                "vulnerability": {
                    "name": "CVE-2023-5678",
                    "description": "Critical vulnerability",
                },
                "__scan_id": "scan-123",
            },
        ]

        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the scan result exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield sca_scan_result_data

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sca_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sca_scan_result_webhook_processor.handle_event(
                payload, sca_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == sca_scan_result_data[0]
        assert result.updated_raw_results[1] == sca_scan_result_data[1]

    async def test_handle_event_empty_results(
        self,
        sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor,
        sca_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test handling when no SCA scan results are found."""
        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the scan result exporter to return empty results
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []  # Empty results

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sca_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sca_scan_result_webhook_processor.handle_event(
                payload, sca_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_exporter_error(
        self,
        sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor,
        sca_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test handling when the exporter raises an error."""
        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the scan result exporter to raise an exception
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources_raises_error(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            raise Exception("API Error")
            yield []  # This line will never be reached

        mock_exporter.get_paginated_resources = (
            mock_get_paginated_resources_raises_error
        )

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sca_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await sca_scan_result_webhook_processor.handle_event(
                    payload, sca_scan_result_resource_config
                )

    async def test_handle_event_multiple_batches(
        self,
        sca_scan_result_webhook_processor: ScaScanResultWebhookProcessor,
        sca_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test handling SCA scan result event with multiple batches."""
        batch1 = [
            {
                "id": "sca-result-1",
                "scan_id": "scan-123",
                "severity": "HIGH",
                "__scan_id": "scan-123",
            },
        ]
        batch2 = [
            {
                "id": "sca-result-2",
                "scan_id": "scan-123",
                "severity": "CRITICAL",
                "__scan_id": "scan-123",
            },
        ]

        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the scan result exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield batch1
            yield batch2

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sca_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sca_scan_result_webhook_processor.handle_event(
                payload, sca_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == batch1[0]
        assert result.updated_raw_results[1] == batch2[0]
