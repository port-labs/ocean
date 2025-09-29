import pytest
from unittest.mock import AsyncMock, patch

from okta.webhook_processors.group_webhook_processor import OktaGroupWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)


def _group_resource_config() -> ResourceConfig:
    selector = Selector(query="true")
    port = PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".id",
                title=".profile.name",
                blueprint="oktaGroup",
                properties={},
            )
        )
    )
    return ResourceConfig(kind="okta-group", selector=selector, port=port)


@pytest.mark.asyncio
async def test_group_processor_delete_event() -> None:
    processor = OktaGroupWebhookProcessor(event=WebhookEvent(trace_id="t", payload={}, headers={}))
    payload = {
        "data": {
            "events": [
                {
                    "eventType": "group.lifecycle.delete",
                    "target": [{"type": "UserGroup", "id": "g1"}],
                }
            ]
        }
    }

    result = await processor.handle_event(payload, _group_resource_config())
    assert isinstance(result, WebhookEventRawResults)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "g1"}]


@pytest.mark.asyncio
async def test_group_processor_upsert_event_calls_exporter() -> None:
    processor = OktaGroupWebhookProcessor(event=WebhookEvent(trace_id="t", payload={}, headers={}))
    payload = {
        "data": {
            "events": [
                {
                    "eventType": "group.profile.update",
                    "target": [
                        {"type": "UserGroup", "id": "g1"},
                        {"type": "UserGroup", "id": "g2"},
                    ],
                }
            ]
        }
    }

    with patch("okta.webhook_processors.group_webhook_processor.OktaClientFactory.get_client") as get_client, patch(
        "okta.webhook_processors.group_webhook_processor.OktaGroupExporter"
    ) as exporter_cls:
        mock_client = object()
        get_client.return_value = mock_client
        exporter = exporter_cls.return_value
        exporter.get_resource = AsyncMock(side_effect=[{"id": "g1"}, {"id": "g2"}])

        res = await processor.handle_event(payload, _group_resource_config())
        assert res.updated_raw_results == [{"id": "g1"}, {"id": "g2"}]
        assert res.deleted_raw_results == []
        assert exporter.get_resource.await_count == 2


