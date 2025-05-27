import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Generator
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.services import ServiceWebhookProcessor
from webhook_processors.incidents import IncidentWebhookProcessor
from kinds import Kinds
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "token": "asdfaaaaa",
            "api_url": "https://test-url.com",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://ingest-test-url.com"
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def service_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ServiceWebhookProcessor:
    return ServiceWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def incident_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> IncidentWebhookProcessor:
    return IncidentWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def mock_client() -> Generator[MagicMock, None, None]:
    with patch("webhook_processors.services.PagerDutyClient") as mock:
        client = MagicMock()
        mock.from_ocean_configuration.return_value = client
        yield client


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=Kinds.SERVICES,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"pagerdutyService"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestServiceWebhookProcessor:
    async def test_should_process_event_upsert(
        self, service_webhook_processor: ServiceWebhookProcessor, mock_client: MagicMock
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "service.created"}},
            headers={},
        )
        result = await service_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_delete(
        self, service_webhook_processor: ServiceWebhookProcessor, mock_client: MagicMock
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "service.deleted"}},
            headers={},
        )
        result = await service_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_other(
        self, service_webhook_processor: ServiceWebhookProcessor, mock_client: MagicMock
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "incident.triggered"}},
            headers={},
        )
        result = await service_webhook_processor.should_process_event(event)
        assert result is False

    async def test_get_matching_kinds(
        self, service_webhook_processor: ServiceWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        kinds = await service_webhook_processor.get_matching_kinds(event)
        assert kinds == [Kinds.SERVICES]

    async def test_handle_event_delete(
        self,
        service_webhook_processor: ServiceWebhookProcessor,
        mock_client: MagicMock,
        resource_config: ResourceConfig,
    ) -> None:
        event_data = {"id": "SERVICE123", "name": "Test Service"}
        payload = {"event": {"event_type": "service.deleted", "data": event_data}}

        result = await service_webhook_processor.handle_event(payload, resource_config)
        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [event_data]

    async def test_handle_event_upsert(
        self,
        service_webhook_processor: ServiceWebhookProcessor,
        mock_client: MagicMock,
        resource_config: ResourceConfig,
    ) -> None:
        service_id = "SERVICE123"
        service_data = {
            "id": service_id,
            "name": "Test Service",
            "escalation_policy": {"id": "EP123"},
        }

        # Mock the API responses
        mock_client.get_single_resource = AsyncMock(
            return_value={"service": service_data}
        )
        mock_client.update_oncall_users = AsyncMock(return_value=[service_data])

        payload = {
            "event": {"event_type": "service.created", "data": {"id": service_id}}
        }

        result = await service_webhook_processor.handle_event(payload, resource_config)
        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [service_data]
        assert result.deleted_raw_results == []

        # Verify the client methods were called correctly
        mock_client.get_single_resource.assert_called_once_with(
            object_type=Kinds.SERVICES, identifier=service_id
        )
        mock_client.update_oncall_users.assert_called_once_with([service_data])


@pytest.mark.asyncio
class TestIncidentWebhookProcessor:
    async def test_should_process_event_triggered(
        self,
        incident_webhook_processor: IncidentWebhookProcessor,
        mock_client: MagicMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "incident.triggered"}},
            headers={},
        )
        result = await incident_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_acknowledged(
        self,
        incident_webhook_processor: IncidentWebhookProcessor,
        mock_client: MagicMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "incident.acknowledged"}},
            headers={},
        )
        result = await incident_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_resolved(
        self,
        incident_webhook_processor: IncidentWebhookProcessor,
        mock_client: MagicMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "incident.resolved"}},
            headers={},
        )
        result = await incident_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_other(
        self,
        incident_webhook_processor: IncidentWebhookProcessor,
        mock_client: MagicMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": {"event_type": "service.created"}},
            headers={},
        )
        result = await incident_webhook_processor.should_process_event(event)
        assert result is False

    async def test_get_matching_kinds(
        self, incident_webhook_processor: IncidentWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        kinds = await incident_webhook_processor.get_matching_kinds(event)
        assert kinds == [Kinds.INCIDENTS]

    async def test_handle_event(
        self,
        incident_webhook_processor: IncidentWebhookProcessor,
        mock_client: MagicMock,
        resource_config: ResourceConfig,
    ) -> None:
        incident_id = "INC123"
        incident_data = {
            "id": incident_id,
            "title": "Test Incident",
            "status": "triggered",
        }

        # Mock the API responses
        mock_client.get_single_resource = AsyncMock(
            return_value={"incident": incident_data}
        )
        mock_client.enrich_incidents_with_analytics_data = AsyncMock(
            return_value=[incident_data]
        )

        payload = {
            "event": {"event_type": "incident.triggered", "data": {"id": incident_id}}
        }
        with patch(
            "clients.pagerduty.PagerDutyClient.from_ocean_configuration",
            return_value=mock_client,
        ):
            result = await incident_webhook_processor.handle_event(
                payload, resource_config
            )
            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [incident_data]
            assert result.deleted_raw_results == []

        # Verify the client methods were called correctly
        mock_client.get_single_resource.assert_called_once_with(
            object_type=Kinds.INCIDENTS, identifier=incident_id
        )
        mock_client.enrich_incidents_with_analytics_data.assert_called_once_with(
            [incident_data]
        )
