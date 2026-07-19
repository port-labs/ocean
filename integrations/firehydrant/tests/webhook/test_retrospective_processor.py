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
from webhook.webhook_processors.retrospective_webhook_processor import (
    RetrospectiveWebhookProcessor,
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

INCIDENT_DATA_POSTMORTEM: dict[str, Any] = {
    **INCIDENT_DATA,
    "current_milestone": "postmortem_completed",
    "report_id": "rep-456",
}

RETROSPECTIVE_DATA: dict[str, Any] = {
    "id": "rep-456",
    "name": "Production outage retrospective",
    "__incident": {"tasks": []},
}


@pytest.fixture
def retrospective_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.RETROSPECTIVE,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"firehydrantRetrospective"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> RetrospectiveWebhookProcessor:
    return RetrospectiveWebhookProcessor(mock_webhook_event)


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook.webhook_processors.retrospective_webhook_processor.init_client"
    ) as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.mark.asyncio
class TestRetrospectiveWebhookProcessor:
    async def test_should_process_event_with_incident(
        self, processor: RetrospectiveWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="t", headers={}, payload=INCIDENT_PAYLOAD)
        assert await processor.should_process_event(event) is True

    async def test_should_not_process_event_without_incident(
        self, processor: RetrospectiveWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t", headers={}, payload={"data": {"environments": []}}
        )
        assert await processor.should_process_event(event) is False

    async def test_get_matching_kinds(
        self, processor: RetrospectiveWebhookProcessor
    ) -> None:
        kinds = await processor.get_matching_kinds(processor.event)
        assert kinds == [ObjectKind.RETROSPECTIVE]

    async def test_handle_event_retrospective_kind_not_completed(
        self,
        processor: RetrospectiveWebhookProcessor,
        mock_client: AsyncMock,
        retrospective_resource_config: ResourceConfig,
    ) -> None:
        mock_client.get_single_incident.return_value = INCIDENT_DATA

        result = await processor.handle_event(
            INCIDENT_PAYLOAD, retrospective_resource_config
        )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_client.get_single_retrospective.assert_not_called()

    async def test_handle_event_retrospective_kind_postmortem_completed(
        self,
        processor: RetrospectiveWebhookProcessor,
        mock_client: AsyncMock,
        retrospective_resource_config: ResourceConfig,
    ) -> None:
        mock_client.get_single_incident.return_value = INCIDENT_DATA_POSTMORTEM
        mock_client.get_single_retrospective.return_value = RETROSPECTIVE_DATA

        result = await processor.handle_event(
            INCIDENT_PAYLOAD, retrospective_resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["id"] == "rep-456"
        assert result.deleted_raw_results == []
        mock_client.get_single_retrospective.assert_awaited_once_with(
            report_id="rep-456"
        )
