from typing import Any, AsyncIterator, List
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor import (
    SastScanResultWebhookProcessor,
)
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    CheckmarxOneSastResourcesConfig,
    CheckmarxOneSastSelector,
)


@pytest.fixture
def sast_scan_result_resource_config() -> CheckmarxOneSastResourcesConfig:
    return CheckmarxOneSastResourcesConfig(
        kind="sast",
        selector=CheckmarxOneSastSelector(
            query="true",
            compliance="PCI-DSS",
            group="SQL Injection",
            include_nodes=True,
            language=["Java", "Python"],
            severity=["critical", "high"],
            status=["new", "recurrent"],
            category="Security",
            state=["to_verify", "not_exploitable"],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".result_id",
                    title=".query_name",
                    blueprint='"checkmarxSastScanResult"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def sast_scan_result_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> SastScanResultWebhookProcessor:
    return SastScanResultWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestSastScanResultWebhookProcessor:

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
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
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
            await sast_scan_result_webhook_processor._should_process_event(event)
            is result
        )

    async def test_get_matching_kinds(
        self, sast_scan_result_webhook_processor: SastScanResultWebhookProcessor
    ) -> None:
        kinds = await sast_scan_result_webhook_processor.get_matching_kinds(
            sast_scan_result_webhook_processor.event
        )
        assert ObjectKind.SAST in kinds

    async def test_authenticate_always_returns_true(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
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
        result = await sast_scan_result_webhook_processor.authenticate(
            valid_payload, headers
        )
        assert result is True

        # Test with invalid payload (missing fields)
        invalid_payload: EventPayload = {
            "scanId": "scan-123",
        }
        result = await sast_scan_result_webhook_processor.authenticate(
            invalid_payload, headers
        )
        assert result is True

        # Test with empty payload
        empty_payload: EventPayload = {}
        result = await sast_scan_result_webhook_processor.authenticate(
            empty_payload, headers
        )
        assert result is True

    async def test_authenticate_returns_true(
        self, sast_scan_result_webhook_processor: SastScanResultWebhookProcessor
    ) -> None:
        """Test that authenticate method returns True."""
        payload: EventPayload = {"scanId": "scan-123", "projectId": "project-456"}
        headers: EventHeaders = {
            "x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED
        }

        result = await sast_scan_result_webhook_processor.authenticate(payload, headers)
        assert result is True

    async def test_should_process_event_with_valid_request(
        self, sast_scan_result_webhook_processor: SastScanResultWebhookProcessor
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
            sast_scan_result_webhook_processor,
            "_verify_webhook_signature",
            return_value=True,
        ):
            result = await sast_scan_result_webhook_processor.should_process_event(
                event
            )
            assert result is True

    async def test_should_process_event_without_request(
        self, sast_scan_result_webhook_processor: SastScanResultWebhookProcessor
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = None

        result = await sast_scan_result_webhook_processor.should_process_event(event)
        assert result is False

    async def test_handle_event_success(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
        sast_scan_result_resource_config: CheckmarxOneSastResourcesConfig,
    ) -> None:
        """Test successful handling of SAST scan result webhook event."""
        sast_scan_result_data = [
            {
                "result_id": "sast-result-1",
                "scan_id": "scan-123",
                "severity": "critical",
                "status": "new",
                "query_id": "query-123",
                "query_name": "Test SAST Query",
                "language": "Java",
                "group": "SQL Injection",
                "compliance": "PCI-DSS",
                "category": "Security",
                "state": "to_verify",
                "confidence_level": "high",
                "cwe_id": "CWE-89",
                "similarity_id": "sim-123",
                "first_found_at": "2024-01-01T00:00:00Z",
                "first_time_scan_id": "scan-001",
                "nodes": [
                    {
                        "node_id": "node-1",
                        "line": 10,
                        "column": 5,
                        "file": "src/main/java/Test.java",
                    }
                ],
                "__scan_id": "scan-123",
            },
            {
                "result_id": "sast-result-2",
                "scan_id": "scan-123",
                "severity": "high",
                "status": "recurrent",
                "query_id": "query-456",
                "query_name": "Critical SAST Query",
                "language": "Python",
                "group": "XSS",
                "compliance": "OWASP",
                "category": "Security",
                "state": "not_exploitable",
                "confidence_level": "medium",
                "cwe_id": "CWE-79",
                "similarity_id": "sim-456",
                "first_found_at": "2024-01-02T00:00:00Z",
                "first_time_scan_id": "scan-002",
                "nodes": [
                    {
                        "node_id": "node-2",
                        "line": 15,
                        "column": 8,
                        "file": "src/app.py",
                    }
                ],
                "__scan_id": "scan-123",
            },
        ]

        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the SAST exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield sast_scan_result_data

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor.create_sast_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sast_scan_result_webhook_processor.handle_event(
                payload, sast_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == sast_scan_result_data[0]
        assert result.updated_raw_results[1] == sast_scan_result_data[1]

    async def test_handle_event_empty_results(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
        sast_scan_result_resource_config: CheckmarxOneSastResourcesConfig,
    ) -> None:
        """Test handling when no SAST scan results are found."""
        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the SAST exporter to return empty results
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []  # Empty results

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor.create_sast_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sast_scan_result_webhook_processor.handle_event(
                payload, sast_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_exporter_error(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
        sast_scan_result_resource_config: CheckmarxOneSastResourcesConfig,
    ) -> None:
        """Test handling when the exporter raises an error."""
        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the SAST exporter to raise an exception
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
                "checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor.create_sast_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await sast_scan_result_webhook_processor.handle_event(
                    payload, sast_scan_result_resource_config
                )

    async def test_handle_event_multiple_batches(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
        sast_scan_result_resource_config: CheckmarxOneSastResourcesConfig,
    ) -> None:
        """Test handling SAST scan result event with multiple batches."""
        batch1 = [
            {
                "result_id": "sast-result-1",
                "scan_id": "scan-123",
                "severity": "critical",
                "query_id": "query-123",
                "language": "Java",
                "__scan_id": "scan-123",
            },
        ]
        batch2 = [
            {
                "result_id": "sast-result-2",
                "scan_id": "scan-123",
                "severity": "high",
                "query_id": "query-456",
                "language": "Python",
                "__scan_id": "scan-123",
            },
        ]

        payload: EventPayload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the SAST exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield batch1
            yield batch2

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor.create_sast_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sast_scan_result_webhook_processor.handle_event(
                payload, sast_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == batch1[0]
        assert result.updated_raw_results[1] == batch2[0]

    async def test_handle_event_with_different_selector_options(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
    ) -> None:
        """Test handling with different selector options."""
        # Create a resource config with different selector options
        resource_config = CheckmarxOneSastResourcesConfig(
            kind="sast",
            selector=CheckmarxOneSastSelector(
                query="true",
                compliance="OWASP",
                group="Authentication",
                include_nodes=False,
                language=["JavaScript"],
                severity=["medium", "low"],
                status=["fixed"],
                category="Authentication",
                state=["proposed_not_exploitable"],
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".result_id",
                        title=".query_name",
                        blueprint='"checkmarxSastScanResult"',
                        properties={},
                    )
                )
            ),
        )

        payload: EventPayload = {
            "scanId": "scan-456",
            "projectId": "project-789",
        }

        # Mock the SAST exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor.create_sast_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sast_scan_result_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_with_minimal_selector_options(
        self,
        sast_scan_result_webhook_processor: SastScanResultWebhookProcessor,
    ) -> None:
        """Test handling with minimal selector options (only scan_id)."""
        # Create a resource config with minimal selector options
        resource_config = CheckmarxOneSastResourcesConfig(
            kind="sast",
            selector=CheckmarxOneSastSelector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".result_id",
                        title=".query_name",
                        blueprint='"checkmarxSastScanResult"',
                        properties={},
                    )
                )
            ),
        )

        payload: EventPayload = {
            "scanId": "scan-789",
            "projectId": "project-999",
        }

        # Mock the SAST exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield [
                {
                    "result_id": "sast-result-minimal",
                    "scan_id": "scan-789",
                    "severity": "info",
                    "query_id": "query-minimal",
                    "__scan_id": "scan-789",
                }
            ]

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor.create_sast_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await sast_scan_result_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["result_id"] == "sast-result-minimal"
