from typing import Any, AsyncIterator, List
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor import (
    KicsScanResultWebhookProcessor,
)
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    CheckmarxOneKicsResourcesConfig,
    CheckmarxOneKicsSelector,
)


@pytest.fixture
def kics_scan_result_resource_config() -> CheckmarxOneKicsResourcesConfig:
    return CheckmarxOneKicsResourcesConfig(
        kind="kics",
        selector=CheckmarxOneKicsSelector(
            query="true",
            severity=["HIGH", "CRITICAL"],
            status=["NEW", "RECURRENT"],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"checkmarxKicsScanResult"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def kics_scan_result_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> KicsScanResultWebhookProcessor:
    return KicsScanResultWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestKicsScanResultWebhookProcessor:

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
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
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
            await kics_scan_result_webhook_processor._should_process_event(event)
            is result
        )

    async def test_get_matching_kinds(
        self, kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor
    ) -> None:
        kinds = await kics_scan_result_webhook_processor.get_matching_kinds(
            kics_scan_result_webhook_processor.event
        )
        assert ObjectKind.KICS in kinds

    async def test_authenticate_always_returns_true(
        self,
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
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
        result = await kics_scan_result_webhook_processor.authenticate(
            valid_payload, headers
        )
        assert result is True

        # Test with invalid payload (missing fields)
        invalid_payload: EventPayload = {
            "scanId": "scan-123",
        }
        result = await kics_scan_result_webhook_processor.authenticate(
            invalid_payload, headers
        )
        assert result is True

        # Test with empty payload
        empty_payload: EventPayload = {}
        result = await kics_scan_result_webhook_processor.authenticate(
            empty_payload, headers
        )
        assert result is True

    async def test_authenticate_returns_true(
        self, kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor
    ) -> None:
        """Test that authenticate method returns True."""
        payload: EventPayload = {"scanId": "scan-123", "projectId": "project-456"}
        headers: EventHeaders = {
            "x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED
        }

        result = await kics_scan_result_webhook_processor.authenticate(payload, headers)
        assert result is True

    async def test_should_process_event_with_valid_request(
        self, kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor
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
            kics_scan_result_webhook_processor,
            "_verify_webhook_signature",
            return_value=True,
        ):
            result = await kics_scan_result_webhook_processor.should_process_event(
                event
            )
            assert result is True

    async def test_should_process_event_without_request(
        self, kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = None

        result = await kics_scan_result_webhook_processor.should_process_event(event)
        assert result is False

    async def test_handle_event_success(
        self,
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
        kics_scan_result_resource_config: CheckmarxOneKicsResourcesConfig,
    ) -> None:
        """Test successful handling of KICS scan result webhook event."""
        kics_scan_result_data = [
            {
                "id": "kics-result-1",
                "scan_id": "scan-123",
                "severity": "HIGH",
                "status": "NEW",
                "query_id": "query-123",
                "query_name": "Test KICS Query",
                "file": "test.yaml",
                "line": 10,
                "__scan_id": "scan-123",
            },
            {
                "id": "kics-result-2",
                "scan_id": "scan-123",
                "severity": "CRITICAL",
                "status": "RECURRENT",
                "query_id": "query-456",
                "query_name": "Critical KICS Query",
                "file": "test.json",
                "line": 5,
                "__scan_id": "scan-123",
            },
        ]

        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the KICS exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield kics_scan_result_data

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor.create_kics_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await kics_scan_result_webhook_processor.handle_event(
                payload, kics_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == kics_scan_result_data[0]
        assert result.updated_raw_results[1] == kics_scan_result_data[1]

    async def test_handle_event_empty_results(
        self,
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
        kics_scan_result_resource_config: CheckmarxOneKicsResourcesConfig,
    ) -> None:
        """Test handling when no KICS scan results are found."""
        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the KICS exporter to return empty results
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []  # Empty results

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor.create_kics_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await kics_scan_result_webhook_processor.handle_event(
                payload, kics_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_exporter_error(
        self,
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
        kics_scan_result_resource_config: CheckmarxOneKicsResourcesConfig,
    ) -> None:
        """Test handling when the exporter raises an error."""
        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the KICS exporter to raise an exception
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
                "checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor.create_kics_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await kics_scan_result_webhook_processor.handle_event(
                    payload, kics_scan_result_resource_config
                )

    async def test_handle_event_multiple_batches(
        self,
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
        kics_scan_result_resource_config: CheckmarxOneKicsResourcesConfig,
    ) -> None:
        """Test handling KICS scan result event with multiple batches."""
        batch1 = [
            {
                "id": "kics-result-1",
                "scan_id": "scan-123",
                "severity": "HIGH",
                "query_id": "query-123",
                "__scan_id": "scan-123",
            },
        ]
        batch2 = [
            {
                "id": "kics-result-2",
                "scan_id": "scan-123",
                "severity": "CRITICAL",
                "query_id": "query-456",
                "__scan_id": "scan-123",
            },
        ]

        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the KICS exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield batch1
            yield batch2

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor.create_kics_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await kics_scan_result_webhook_processor.handle_event(
                payload, kics_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == batch1[0]
        assert result.updated_raw_results[1] == batch2[0]

    async def test_handle_event_with_different_selector_options(
        self,
        kics_scan_result_webhook_processor: KicsScanResultWebhookProcessor,
    ) -> None:
        """Test handling with different selector options."""
        # Create a resource config with different selector options
        resource_config = CheckmarxOneKicsResourcesConfig(
            kind="kics",
            selector=CheckmarxOneKicsSelector(
                query="true",
                severity=["LOW", "MEDIUM"],
                status=["FIXED"],
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".id",
                        blueprint='"checkmarxKicsScanResult"',
                        properties={},
                    )
                )
            ),
        )

        payload: EventPayload = {
            "scanId": "scan-456",
            "projectId": "project-789",
        }

        # Mock the KICS exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor.create_kics_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await kics_scan_result_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
