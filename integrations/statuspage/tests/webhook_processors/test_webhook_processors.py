from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook_processors.incident_update_webhook_processor import (
    IncidentUpdateWebhookProcessor,
)
from webhook_processors.incident_webhook_processor import IncidentWebhookProcessor
from webhook_processors.page_webhook_processor import PageWebhookProcessor


class TestPageWebhookProcessor:
    def _create_processor(self, payload: dict[str, Any]) -> PageWebhookProcessor:
        event = WebhookEvent(trace_id="test-trace-id", payload=payload, headers={})
        return PageWebhookProcessor(event)

    def _resource_config(self) -> ResourceConfig:
        return cast(ResourceConfig, SimpleNamespace())

    @pytest.mark.asyncio
    async def test_should_process_event_when_page_present(self) -> None:
        processor = self._create_processor({"page": {"id": "page-1"}})
        assert await processor.should_process_event(processor.event) is True

    @pytest.mark.asyncio
    async def test_should_not_process_event_without_page(self) -> None:
        processor = self._create_processor({"incident": {"id": "incident-1"}})
        assert await processor.should_process_event(processor.event) is False

    @pytest.mark.asyncio
    async def test_handle_event_merges_webhook_and_api_page_data(self) -> None:
        processor = self._create_processor(
            {"page": {"id": "page-1", "name": "Status Page"}}
        )
        api_page = {"id": "page-1", "domain": "example.statuspage.io"}
        mock_client = MagicMock()
        mock_client.get_page_by_id = AsyncMock(return_value=api_page)

        with patch(
            "webhook_processors.page_webhook_processor.init_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(
                processor.event.payload, self._resource_config()
            )

        mock_client.get_page_by_id.assert_called_once_with("page-1")
        assert result.updated_raw_results == [
            {"id": "page-1", "name": "Status Page", "domain": "example.statuspage.io"}
        ]
        assert result.deleted_raw_results == []


class TestIncidentWebhookProcessor:
    def _create_processor(self, payload: dict[str, Any]) -> IncidentWebhookProcessor:
        event = WebhookEvent(trace_id="test-trace-id", payload=payload, headers={})
        return IncidentWebhookProcessor(event)

    def _resource_config(self) -> ResourceConfig:
        return cast(ResourceConfig, SimpleNamespace())

    @pytest.mark.asyncio
    async def test_handle_event_returns_incident_from_payload(self) -> None:
        incident = {"id": "incident-1", "name": "API outage"}
        processor = self._create_processor({"incident": incident})

        result = await processor.handle_event(
            processor.event.payload, self._resource_config()
        )

        assert result.updated_raw_results == [incident]
        assert result.deleted_raw_results == []


class TestIncidentUpdateWebhookProcessor:
    def _create_processor(self, payload: dict[str, Any]) -> IncidentUpdateWebhookProcessor:
        event = WebhookEvent(trace_id="test-trace-id", payload=payload, headers={})
        return IncidentUpdateWebhookProcessor(event)

    def _resource_config(self) -> ResourceConfig:
        return cast(ResourceConfig, SimpleNamespace())

    @pytest.mark.asyncio
    async def test_should_process_event_when_incident_updates_present(self) -> None:
        processor = self._create_processor(
            {"incident": {"id": "incident-1", "incident_updates": [{"id": "update-1"}]}}
        )
        assert await processor.should_process_event(processor.event) is True

    @pytest.mark.asyncio
    async def test_handle_event_returns_incident_updates(self) -> None:
        incident_updates = [{"id": "update-1"}, {"id": "update-2"}]
        processor = self._create_processor(
            {"incident": {"id": "incident-1", "incident_updates": incident_updates}}
        )

        result = await processor.handle_event(
            processor.event.payload, self._resource_config()
        )

        assert result.updated_raw_results == incident_updates
        assert result.deleted_raw_results == []
