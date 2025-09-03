from typing import Any, AsyncIterator, Dict, List
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.api_security_webhook_processor import (
    ApiSecurityWebhookProcessor,
)
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import CheckmarxOneApiSecResourcesConfig, CheckmarxOneApiSecSelector


@pytest.fixture
def api_sec_resource_config() -> CheckmarxOneApiSecResourcesConfig:
    return CheckmarxOneApiSecResourcesConfig(
        kind="api-security",
        selector=CheckmarxOneApiSecSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint='"checkmarxApiSec"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def api_sec_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ApiSecurityWebhookProcessor:
    return ApiSecurityWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestApiSecurityWebhookProcessor:

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
        api_sec_webhook_processor: ApiSecurityWebhookProcessor,
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

        assert await api_sec_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, api_sec_webhook_processor: ApiSecurityWebhookProcessor
    ) -> None:
        kinds = await api_sec_webhook_processor.get_matching_kinds(
            api_sec_webhook_processor.event
        )
        assert ObjectKind.API_SEC in kinds

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
        api_sec_webhook_processor: ApiSecurityWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await api_sec_webhook_processor.validate_payload(payload)
        assert result is expected

    async def test_handle_event_success(
        self,
        api_sec_webhook_processor: ApiSecurityWebhookProcessor,
        api_sec_resource_config: CheckmarxOneApiSecResourcesConfig,
    ) -> None:
        """Test handling an API security event successfully."""
        api_sec_data_batch_1 = [
            {
                "id": "risk-1",
                "scan_id": "scan-123",
                "severity": "high",
                "status": "open",
                "created_at": "2023-01-01T00:00:00Z",
                "__scan_id": "scan-123",
            },
            {
                "id": "risk-2",
                "scan_id": "scan-123",
                "severity": "medium",
                "status": "open",
                "created_at": "2023-01-01T00:00:00Z",
                "__scan_id": "scan-123",
            },
        ]

        api_sec_data_batch_2 = [
            {
                "id": "risk-3",
                "scan_id": "scan-123",
                "severity": "low",
                "status": "open",
                "created_at": "2023-01-01T00:00:00Z",
                "__scan_id": "scan-123",
            },
        ]

        payload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the API sec exporter
        mock_exporter = AsyncMock()

        # Create an async generator that yields the batches
        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield api_sec_data_batch_1
            yield api_sec_data_batch_2

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.api_security_webhook_processor.create_api_sec_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await api_sec_webhook_processor.handle_event(
                payload, api_sec_resource_config
            )

            # Verify exporter was called with correct parameters
            mock_create_exporter.assert_called_once()

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 3  # Total of all batches
        assert len(result.deleted_raw_results) == 0

        # Verify all items from both batches are included
        expected_ids = {"risk-1", "risk-2", "risk-3"}
        actual_ids = {item["id"] for item in result.updated_raw_results}
        assert actual_ids == expected_ids

    async def test_handle_event_empty_results(
        self,
        api_sec_webhook_processor: ApiSecurityWebhookProcessor,
        api_sec_resource_config: CheckmarxOneApiSecResourcesConfig,
    ) -> None:
        """Test handling an API security event with empty results."""
        payload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the API sec exporter to return empty results
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield []  # Empty batch

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.api_security_webhook_processor.create_api_sec_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await api_sec_webhook_processor.handle_event(
                payload, api_sec_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_exporter_error(
        self,
        api_sec_webhook_processor: ApiSecurityWebhookProcessor,
        api_sec_resource_config: CheckmarxOneApiSecResourcesConfig,
    ) -> None:
        """Test handling when the exporter raises an error."""
        payload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the API sec exporter to raise an exception
        mock_exporter = AsyncMock()

        # Create an async generator that raises an exception
        async def mock_get_paginated_resources_error(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            raise Exception("API Error")
            if False:  # ensure async generator type
                yield []

        mock_exporter.get_paginated_resources = mock_get_paginated_resources_error

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.api_security_webhook_processor.create_api_sec_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await api_sec_webhook_processor.handle_event(
                    payload, api_sec_resource_config
                )

    async def test_handle_event_single_batch(
        self,
        api_sec_webhook_processor: ApiSecurityWebhookProcessor,
        api_sec_resource_config: CheckmarxOneApiSecResourcesConfig,
    ) -> None:
        """Test handling an API security event with a single batch."""
        api_sec_data = [
            {
                "id": "risk-1",
                "scan_id": "scan-123",
                "severity": "high",
                "status": "open",
                "created_at": "2023-01-01T00:00:00Z",
                "__scan_id": "scan-123",
            },
        ]

        payload = {
            "scanId": "scan-123",
            "projectId": "project-456",
        }

        # Mock the API sec exporter
        mock_exporter = AsyncMock()

        async def mock_get_paginated_resources(
            options: Any,
        ) -> AsyncIterator[List[dict[str, Any]]]:
            yield api_sec_data

        mock_exporter.get_paginated_resources = mock_get_paginated_resources

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.api_security_webhook_processor.create_api_sec_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await api_sec_webhook_processor.handle_event(
                payload, api_sec_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == api_sec_data[0]

    async def test_authenticate_returns_true(
        self, api_sec_webhook_processor: ApiSecurityWebhookProcessor
    ) -> None:
        """Test that authenticate method returns True."""
        payload = EventPayload({"scanId": "scan-123", "projectId": "project-456"})
        headers = EventHeaders(
            {"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED}
        )

        result = await api_sec_webhook_processor.authenticate(payload, headers)
        assert result is True

    async def test_should_process_event_with_valid_request(
        self, api_sec_webhook_processor: ApiSecurityWebhookProcessor
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
            api_sec_webhook_processor, "_verify_webhook_signature", return_value=True
        ):
            result = await api_sec_webhook_processor.should_process_event(event)
            assert result is True

    async def test_should_process_event_without_request(
        self, api_sec_webhook_processor: ApiSecurityWebhookProcessor
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"scanId": "scan-123", "projectId": "project-456"},
            headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
        )
        event._original_request = None

        result = await api_sec_webhook_processor.should_process_event(event)
        assert result is False
