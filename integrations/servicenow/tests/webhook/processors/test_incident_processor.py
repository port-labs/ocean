import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
    ResourceConfig,
    Selector,
)
from webhook.processors.incident_processor import IncidentWebhookProcessor
from integration import ObjectKind
from tests.conftest import SAMPLE_INCIDENT_DATA


@pytest.fixture
def resource_config() -> ResourceConfig:
    """Create a resource config fixture for incident."""
    return ResourceConfig(
        kind="incident",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".sys_id",
                    title=".number",
                    blueprint='"servicenowIncident"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def incident_processor(
    mock_webhook_event: WebhookEvent,
) -> IncidentWebhookProcessor:
    """Create an incident webhook processor fixture."""
    return IncidentWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestIncidentWebhookProcessor:
    """Test suite for IncidentWebhookProcessor."""

    async def test_get_matching_kinds(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the correct kind."""
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await incident_processor.get_matching_kinds(mock_event)

        assert kinds == [ObjectKind.INCIDENT]
        assert kinds == ["incident"]

    async def test_should_process_event_valid_incident(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns True for incident events."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        result = incident_processor._should_process_event(mock_event)

        assert result is True

    async def test_should_process_event_invalid_class(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns False for non-incident events."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_class_name": "sys_user_group", "sys_id": "test123"}

        result = incident_processor._should_process_event(mock_event)

        assert result is False

    async def test_should_process_event_missing_class(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns False when sys_class_name is missing."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_id": "test123"}

        result = incident_processor._should_process_event(mock_event)

        assert result is False

    async def test_handle_event_incident_found(
        self,
        incident_processor: IncidentWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling an event when the incident is found in ServiceNow."""
        payload = {
            "sys_id": SAMPLE_INCIDENT_DATA["sys_id"],
            "sys_class_name": "incident",
        }

        # Mock the webhook client and its response
        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=SAMPLE_INCIDENT_DATA)

        with patch(
            "webhook.processors.incident_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await incident_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [SAMPLE_INCIDENT_DATA]
            assert result.deleted_raw_results == []

            mock_client.get_record_by_sys_id.assert_called_once_with(
                ObjectKind.INCIDENT, SAMPLE_INCIDENT_DATA["sys_id"]
            )

    async def test_handle_event_incident_deleted(
        self,
        incident_processor: IncidentWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling an event when the incident is not found (deleted)."""
        payload = {
            "sys_id": "deleted_incident_id",
            "sys_class_name": "incident",
        }

        # Mock the webhook client returning None (not found)
        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=None)

        with patch(
            "webhook.processors.incident_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await incident_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == [payload]

            mock_client.get_record_by_sys_id.assert_called_once_with(
                ObjectKind.INCIDENT, "deleted_incident_id"
            )


@pytest.mark.asyncio
class TestIncidentWebhookProcessorBaseClass:
    """Test suite for base class methods inherited by IncidentWebhookProcessor."""

    async def test_authenticate_always_returns_true(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that authenticate always returns True (no auth required)."""
        result = await incident_processor.authenticate({}, {})

        assert result is True

    async def test_validate_payload_with_sys_id(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that validate_payload returns True when sys_id is present."""
        payload = {"sys_id": "test123", "sys_class_name": "incident"}

        result = await incident_processor.validate_payload(payload)

        assert result is True

    async def test_validate_payload_missing_sys_id(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test that validate_payload returns False when sys_id is missing."""
        payload = {"sys_class_name": "incident", "number": "INC001"}

        result = await incident_processor.validate_payload(payload)

        assert result is False

    async def test_should_process_event_with_headers(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test should_process_event checks for ServiceNow integration header."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        result = await incident_processor.should_process_event(mock_event)

        assert result is True

    async def test_should_process_event_missing_header(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test should_process_event returns False without ServiceNow header."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {}
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        result = await incident_processor.should_process_event(mock_event)

        assert result is False

    async def test_should_process_event_no_original_request(
        self, incident_processor: IncidentWebhookProcessor
    ) -> None:
        """Test should_process_event returns False without original request."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = None
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        result = await incident_processor.should_process_event(mock_event)

        assert result is False
