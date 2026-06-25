from types import SimpleNamespace
from typing import Any, cast

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook.webhook_processors.incident_webhook_processor import (
    IncidentWebhookProcessor,
)


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
