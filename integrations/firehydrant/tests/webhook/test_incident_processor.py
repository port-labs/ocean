from typing import Any, Generator
from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from utils import ObjectKind
from webhook.webhook_processors.incident_webhook_processor import (
    IncidentWebhookProcessor,
)


INCIDENT_PAYLOAD: dict[str, Any] = {
    "data": {
        "incident": {"id": "inc-123"},
    }
}

INCIDENT_DATA: dict[str, Any] = {
    "id": "inc-123",
    "name": "Production outage",
    "current_milestone": "started",
    "report_id": None,
}


@pytest.fixture
def incident_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.INCIDENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"firehydrantIncident"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> IncidentWebhookProcessor:
    return IncidentWebhookProcessor(mock_webhook_event)


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook.webhook_processors.incident_webhook_processor.init_client"
    ) as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.mark.asyncio
class TestIncidentWebhookProcessor:
    async def test_should_process_event_with_incident(
        self, processor: IncidentWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="t", headers={}, payload=INCIDENT_PAYLOAD)
        assert await processor.should_process_event(event) is True

    async def test_should_not_process_event_without_incident(
        self, processor: IncidentWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t", headers={}, payload={"data": {"environments": []}}
        )
        assert await processor.should_process_event(event) is False

    async def test_get_matching_kinds(
        self, processor: IncidentWebhookProcessor
    ) -> None:
        kinds = await processor.get_matching_kinds(processor.event)
        assert kinds == [ObjectKind.INCIDENT]

    async def test_handle_event_incident_kind(
        self,
        processor: IncidentWebhookProcessor,
        mock_client: AsyncMock,
        incident_resource_config: ResourceConfig,
    ) -> None:
        mock_client.get_single_incident.return_value = INCIDENT_DATA

        result = await processor.handle_event(
            INCIDENT_PAYLOAD, incident_resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "inc-123"
        assert result.deleted_raw_results == []
