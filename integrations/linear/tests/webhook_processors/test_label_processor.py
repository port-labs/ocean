from typing import Any, Dict, Generator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from webhook_processors.label_processor import LabelWebhookProcessor
from kinds import ObjectKind


@pytest.fixture
def label_processor(mock_webhook_event: WebhookEvent) -> LabelWebhookProcessor:
    return LabelWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def valid_label_payload() -> Dict[str, Any]:
    return {
        "type": "IssueLabel",
        "data": {"id": "label-123", "name": "Bug", "color": "#FF0000"},
    }


@pytest.fixture
def invalid_label_payload() -> Dict[str, Any]:
    return {
        "type": "IssueLabel",
        "data": {"name": "Bug", "color": "#FF0000"},  # Missing id
    }


@pytest.fixture
def non_label_payload() -> Dict[str, Any]:
    return {"type": "Issue", "data": {"identifier": "ABC-123", "title": "Test Issue"}}


@pytest.fixture
def mock_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.LABEL,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"linearLabel"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch("webhook_processors.label_processor.LinearClient") as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestLabelWebhookProcessor:
    async def test_should_process_event_valid_payload(
        self,
        label_processor: LabelWebhookProcessor,
        valid_label_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=valid_label_payload, headers={})
        event._original_request = MagicMock()
        should_process = await label_processor.should_process_event(event)
        assert should_process is True

    async def test_should_process_event_invalid_payload(
        self,
        label_processor: LabelWebhookProcessor,
        invalid_label_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=invalid_label_payload, headers={})
        should_process = await label_processor.should_process_event(event)
        assert should_process is False

    async def test_should_process_event_non_label_payload(
        self, label_processor: LabelWebhookProcessor, non_label_payload: dict[str, Any]
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=non_label_payload, headers={})
        should_process = await label_processor.should_process_event(event)
        assert should_process is False

    async def test_get_matching_kinds(
        self,
        label_processor: LabelWebhookProcessor,
        valid_label_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(trace_id="test", payload=valid_label_payload, headers={})
        kinds = await label_processor.get_matching_kinds(event)
        assert kinds == ["label"]

    async def test_handle_event_success(
        self,
        mock_client: AsyncMock,
        label_processor: LabelWebhookProcessor,
        valid_label_payload: dict[str, Any],
        mock_resource_config: ResourceConfig,
    ) -> None:
        # Mock response data
        mock_label_data = {
            "id": "label-123",
            "name": "Bug",
            "color": "#FF0000",
            "description": "Bug label",
        }
        mock_client.get_single_label.return_value = mock_label_data

        # Process the event
        result = await label_processor.handle_event(
            valid_label_payload, mock_resource_config
        )

        # Verify the results
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_label_data
        assert len(result.deleted_raw_results) == 0

        mock_client.get_single_label.assert_called_once_with("label-123")
