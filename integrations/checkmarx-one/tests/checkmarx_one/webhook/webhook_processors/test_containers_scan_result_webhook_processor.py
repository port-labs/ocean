from typing import Any, AsyncIterator, List
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor import (
    ContainersScanResultWebhookProcessor,
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
def containers_scan_result_resource_config() -> CheckmarxOneScanResultResourcesConfig:
    return CheckmarxOneScanResultResourcesConfig(
        kind="containers",
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
                    blueprint='"checkmarxContainersScanResult"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def containers_scan_result_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ContainersScanResultWebhookProcessor:
    return ContainersScanResultWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestContainersScanResultWebhookProcessor:

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
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
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
            await containers_scan_result_webhook_processor._should_process_event(event)
            is result
        )

    async def test_get_matching_kinds(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
    ) -> None:
        kinds = await containers_scan_result_webhook_processor.get_matching_kinds(
            containers_scan_result_webhook_processor.event
        )
        assert ScanResultObjectKind.CONTAINERS in kinds

    async def test_authenticate_always_returns_true(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
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
        result = await containers_scan_result_webhook_processor.authenticate(
            valid_payload, headers
        )
        assert result is True

        # Test with invalid payload (missing fields)
        invalid_payload: EventPayload = {
            "scanId": "scan-123",
        }
        result = await containers_scan_result_webhook_processor.authenticate(
            invalid_payload, headers
        )
        assert result is True

        # Test with empty payload
        empty_payload: EventPayload = {}
        result = await containers_scan_result_webhook_processor.authenticate(
            empty_payload, headers
        )
        assert result is True

    async def test_authenticate_returns_true(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
    ) -> None:
        """Test that authenticate method returns True."""
        payload: EventPayload = {"scanId": "scan-123", "projectId": "project-456"}
        headers: EventHeaders = {
            "x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED
        }

        result = await containers_scan_result_webhook_processor.authenticate(
            payload, headers
        )
        assert result is True

    async def test_should_process_event_with_valid_request(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
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
            containers_scan_result_webhook_processor,
            "_verify_webhook_signature",
            return_value=True,
        ):
            result = (
                await containers_scan_result_webhook_processor.should_process_event(
                    event
                )
            )
            assert result is True

    async def test_should_process_event_without_request(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = None

        result = await containers_scan_result_webhook_processor.should_process_event(
            event
        )
        assert result is False

    async def test_handle_event_success(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
        containers_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test successful handling of containers scan result webhook event."""
        containers_scan_result_data = [
            {
                "id": "container-result-1",
                "scan_id": "scan-123",
                "severity": "HIGH",
                "state": "CONFIRMED",
                "status": "NEW",
                "vulnerability": {
                    "name": "CVE-2023-1234",
                    "description": "Container vulnerability",
                },
                "image": {
                    "name": "nginx:latest",
                    "tag": "latest",
                },
                "__scan_id": "scan-123",
            },
            {
                "id": "container-result-2",
                "scan_id": "scan-123",
                "severity": "CRITICAL",
                "state": "URGENT",
                "status": "RECURRENT",
                "vulnerability": {
                    "name": "CVE-2023-5678",
                    "description": "Critical container vulnerability",
                },
                "image": {
                    "name": "redis:alpine",
                    "tag": "alpine",
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
            yield containers_scan_result_data

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await containers_scan_result_webhook_processor.handle_event(
                payload, containers_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == containers_scan_result_data[0]
        assert result.updated_raw_results[1] == containers_scan_result_data[1]

    async def test_handle_event_empty_results(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
        containers_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test handling when no containers scan results are found."""
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
                "checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await containers_scan_result_webhook_processor.handle_event(
                payload, containers_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_exporter_error(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
        containers_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
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
                "checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await containers_scan_result_webhook_processor.handle_event(
                    payload, containers_scan_result_resource_config
                )

    async def test_handle_event_multiple_batches(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
        containers_scan_result_resource_config: CheckmarxOneScanResultResourcesConfig,
    ) -> None:
        """Test handling containers scan result event with multiple batches."""
        batch1 = [
            {
                "id": "container-result-1",
                "scan_id": "scan-123",
                "severity": "HIGH",
                "image": {"name": "nginx:latest"},
                "__scan_id": "scan-123",
            },
        ]
        batch2 = [
            {
                "id": "container-result-2",
                "scan_id": "scan-123",
                "severity": "CRITICAL",
                "image": {"name": "redis:alpine"},
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
                "checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await containers_scan_result_webhook_processor.handle_event(
                payload, containers_scan_result_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == batch1[0]
        assert result.updated_raw_results[1] == batch2[0]

    async def test_handle_event_with_different_selector_options(
        self,
        containers_scan_result_webhook_processor: ContainersScanResultWebhookProcessor,
    ) -> None:
        """Test handling with different selector options."""
        # Create a resource config with different selector options
        resource_config = CheckmarxOneScanResultResourcesConfig(
            kind="containers",
            selector=CheckmarxOneResultSelector(
                query="true",
                severity=["LOW", "MEDIUM"],
                state=["FALSE_POSITIVE"],
                status=["FIXED"],
                exclude_result_types="DEV_AND_TEST",
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".id",
                        blueprint='"checkmarxContainersScanResult"',
                        properties={},
                    )
                )
            ),
        )

        payload: EventPayload = {
            "scanId": "scan-456",
            "projectId": "project-789",
        }

        # Mock the scan result exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor.create_scan_result_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await containers_scan_result_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
