from types import SimpleNamespace
from typing import Any, cast

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook.webhook_processors.incident_update_webhook_processor import (
    IncidentUpdateWebhookProcessor,
)


class TestIncidentUpdateWebhookProcessor:
    def _create_processor(
        self, payload: dict[str, Any]
    ) -> IncidentUpdateWebhookProcessor:
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
