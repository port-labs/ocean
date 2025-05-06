import pytest
from unittest.mock import AsyncMock, patch, Mock
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook_processors.resource_webhook_processor import ResourceWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)


@pytest.mark.asyncio
async def test_handle_event_deleted() -> None:
    event = WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")
    resource_config = Mock(spec=ResourceConfig)
    processor = ResourceWebhookProcessor(
        event=event
    )  # Keep this if Base class expects it

    with patch.object(processor, "get_client", return_value=AsyncMock()):
        payload = {
            "Payload": {
                "Event": {
                    "Category": "Deleted",
                    "ChangeDetails": {"DocumentContext": {"Id": "Projects-1"}},
                    "SpaceId": "Spaces-1",
                }
            }
        }

        result = await processor.handle_event(payload, resource_config=resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert result.deleted_raw_results == [{"Id": "Projects-1"}]
        assert result.updated_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_with_resources() -> None:
    event = WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")
    resource_config = Mock(spec=ResourceConfig)
    processor = ResourceWebhookProcessor(event=event)

    mock_client = AsyncMock()
    mock_resource = {"Id": "Projects-1", "Name": "Sample Project"}
    mock_client.get_single_resource.return_value = mock_resource

    with patch.object(processor, "get_client", return_value=mock_client):
        payload = {
            "Payload": {
                "Event": {"SpaceId": "Spaces-1", "RelatedDocumentIds": ["Projects-1"]}
            }
        }

        result = await processor.handle_event(payload, resource_config=resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [mock_resource]
        assert result.deleted_raw_results == []
