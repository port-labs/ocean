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
from webhook.processors.generic_processor import GenericWebhookProcessor
from tests.conftest import SAMPLE_INCIDENT_DATA


@pytest.fixture
def resource_config() -> ResourceConfig:
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
def generic_processor(mock_webhook_event: WebhookEvent) -> GenericWebhookProcessor:
    return GenericWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestGenericWebhookProcessor:

    async def test_get_matching_kinds_with_table_name(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"__table_name": "sys_user_group", "sys_id": "test123"}

        kinds = await generic_processor.get_matching_kinds(mock_event)

        assert kinds == ["sys_user_group"]

    async def test_get_matching_kinds_with_sys_class_name_fallback(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        kinds = await generic_processor.get_matching_kinds(mock_event)

        assert kinds == ["incident"]

    async def test_get_matching_kinds_table_name_takes_priority(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {
            "__table_name": "task",
            "sys_class_name": "change_request",
            "sys_id": "test123",
        }

        kinds = await generic_processor.get_matching_kinds(mock_event)

        assert kinds == ["task"]

    async def test_get_matching_kinds_empty_when_no_table_info(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_id": "test123"}

        kinds = await generic_processor.get_matching_kinds(mock_event)

        assert kinds == []

    async def test_should_process_event_with_table_name(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"__table_name": "sys_user_group", "sys_id": "test123"}

        assert generic_processor._should_process_event(mock_event) is True

    async def test_should_process_event_with_sys_class_name(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        assert generic_processor._should_process_event(mock_event) is True

    async def test_should_process_event_false_without_table_info(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_id": "test123"}

        assert generic_processor._should_process_event(mock_event) is False

    async def test_handle_event_record_found(
        self,
        generic_processor: GenericWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = {
            "sys_id": SAMPLE_INCIDENT_DATA["sys_id"],
            "__table_name": "incident",
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=SAMPLE_INCIDENT_DATA)

        with patch(
            "webhook.processors.generic_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await generic_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [SAMPLE_INCIDENT_DATA]
            assert result.deleted_raw_results == []
            mock_client.get_record_by_sys_id.assert_called_once_with(
                "incident", SAMPLE_INCIDENT_DATA["sys_id"]
            )

    async def test_handle_event_record_deleted(
        self,
        generic_processor: GenericWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = {
            "sys_id": "deleted_id",
            "__table_name": "incident",
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=None)

        with patch(
            "webhook.processors.generic_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await generic_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == [payload]
            mock_client.get_record_by_sys_id.assert_called_once_with(
                "incident", "deleted_id"
            )

    async def test_handle_event_table_name_routing(
        self,
        generic_processor: GenericWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = {
            "sys_id": "group123",
            "__table_name": "sys_user_group",
        }
        group_record = {"sys_id": "group123", "name": "Network Team"}

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=group_record)

        with patch(
            "webhook.processors.generic_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await generic_processor.handle_event(payload, resource_config)

            assert result.updated_raw_results == [group_record]
            mock_client.get_record_by_sys_id.assert_called_once_with(
                "sys_user_group", "group123"
            )

    async def test_handle_event_sys_class_name_fallback(
        self,
        generic_processor: GenericWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = {
            "sys_id": SAMPLE_INCIDENT_DATA["sys_id"],
            "sys_class_name": "incident",
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=SAMPLE_INCIDENT_DATA)

        with patch(
            "webhook.processors.generic_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await generic_processor.handle_event(payload, resource_config)

            assert result.updated_raw_results == [SAMPLE_INCIDENT_DATA]
            mock_client.get_record_by_sys_id.assert_called_once_with(
                "incident", SAMPLE_INCIDENT_DATA["sys_id"]
            )

    async def test_handle_event_no_table_name(
        self,
        generic_processor: GenericWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = {"sys_id": "test123"}

        result = await generic_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


@pytest.mark.asyncio
class TestGenericWebhookProcessorBaseClass:

    async def test_authenticate_no_secret(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        result = await generic_processor.authenticate({}, {})
        assert result is True

    async def test_validate_payload_with_sys_id(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        assert await generic_processor.validate_payload({"sys_id": "test123"}) is True

    async def test_validate_payload_missing_sys_id(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        assert await generic_processor.validate_payload({"number": "INC001"}) is False

    async def test_should_process_event_with_headers(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"__table_name": "incident", "sys_id": "test123"}

        assert await generic_processor.should_process_event(mock_event) is True

    async def test_should_process_event_missing_header(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = True
        mock_event.headers = {}
        mock_event.payload = {"__table_name": "incident", "sys_id": "test123"}

        assert await generic_processor.should_process_event(mock_event) is False

    async def test_should_process_event_no_original_request(
        self, generic_processor: GenericWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event._original_request = None
        mock_event.headers = {"x-snc-integration-source": "business_rule"}
        mock_event.payload = {"__table_name": "incident", "sys_id": "test123"}

        assert await generic_processor.should_process_event(mock_event) is False
