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
from webhook.webhook_processors.service_webhook_processor import (
    ServiceWebhookProcessor,
)


SERVICE_PAYLOAD: dict[str, Any] = {
    "data": {
        "services": [
            {"id": "svc-1"},
            {"id": "svc-2"},
        ]
    }
}

SERVICE_DATA: dict[str, Any] = {
    "id": "svc-1",
    "name": "Payments API",
    "__incidents": {"milestones": []},
}


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.SERVICE,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"firehydrantService"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> ServiceWebhookProcessor:
    return ServiceWebhookProcessor(mock_webhook_event)


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook.webhook_processors.service_webhook_processor.init_client"
    ) as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.mark.asyncio
class TestServiceWebhookProcessor:
    async def test_should_process_event_with_services(
        self, processor: ServiceWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="t", headers={}, payload=SERVICE_PAYLOAD)
        assert await processor.should_process_event(event) is True

    async def test_should_not_process_event_without_services(
        self, processor: ServiceWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="t", headers={}, payload={"data": {"incident": {"id": "inc-1"}}}
        )
        assert await processor.should_process_event(event) is False

    async def test_get_matching_kinds(self, processor: ServiceWebhookProcessor) -> None:
        kinds = await processor.get_matching_kinds(processor.event)
        assert kinds == [ObjectKind.SERVICE]

    async def test_handle_event_returns_all_services(
        self,
        processor: ServiceWebhookProcessor,
        mock_client: AsyncMock,
        resource_config: ResourceConfig,
    ) -> None:
        # get_single_service returns a list (enriched with incident milestones)
        mock_client.get_single_service.return_value = [SERVICE_DATA]

        result = await processor.handle_event(SERVICE_PAYLOAD, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 2
        assert result.deleted_raw_results == []
        assert mock_client.get_single_service.await_count == 2
        mock_client.get_single_service.assert_any_await(service_id="svc-1")
        mock_client.get_single_service.assert_any_await(service_id="svc-2")
