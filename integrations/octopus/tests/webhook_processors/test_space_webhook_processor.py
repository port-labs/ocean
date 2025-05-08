import pytest
from unittest.mock import AsyncMock, Mock, patch
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.space_webhook_processor import SpaceWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
)


@pytest.mark.asyncio
async def test_handle_event_deleted() -> None:
    event = WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")
    resource_config = Mock(spec=ResourceConfig)
    processor = SpaceWebhookProcessor(event=event)
    mock_client = AsyncMock()

    with patch.object(processor, "get_client", return_value=mock_client):
        payload = {
            "Payload": {
                "Event": {
                    "Category": "Deleted",
                    "SpaceId": "Spaces-1",
                }
            }
        }

        result = await processor.handle_event(payload, resource_config=resource_config)
        assert isinstance(result, WebhookEventRawResults)
        assert result.deleted_raw_results == [{"Id": "Spaces-1"}]
        assert result.updated_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_updated() -> None:
    event = WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")
    resource_config = Mock(spec=ResourceConfig)
    processor = SpaceWebhookProcessor(event=event)
    mock_client = AsyncMock()
    mock_space_data = {"Id": "Spaces-1", "Name": "Test Space"}
    mock_client.get_single_space.return_value = mock_space_data

    with patch.object(processor, "get_client", return_value=mock_client):
        payload = {
            "Payload": {
                "Event": {
                    "SpaceId": "Spaces-1",
                }
            }
        }

        result = await processor.handle_event(payload, resource_config=resource_config)
        assert result.updated_raw_results == [mock_space_data]
        assert result.deleted_raw_results == []
