import pytest
from unittest.mock import AsyncMock, patch

from okta.webhook_processors.user_webhook_processor import OktaUserWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults, WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)


def _resource_config() -> ResourceConfig:
    from integration import OktaUserConfig, OktaUserSelector

    selector = OktaUserSelector(
        query="true",
        include_groups=True,
        include_applications=False,
        fields="id,profile.login",
    )
    port = PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".id",
                title=".profile.login",
                blueprint="oktaUser",
                properties={},
            )
        )
    )
    return OktaUserConfig(kind="okta-user", selector=selector, port=port)


@pytest.mark.asyncio
async def test_user_processor_delete_event() -> None:
    processor = OktaUserWebhookProcessor(event=WebhookEvent(trace_id="t", payload={}, headers={}))
    payload = {
        "data": {
            "events": [
                {
                    "eventType": "user.lifecycle.delete.initiated",
                    "target": [{"type": "User", "id": "u1"}],
                }
            ]
        }
    }

    result = await processor.handle_event(payload, _resource_config())
    assert isinstance(result, WebhookEventRawResults)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "u1"}]


@pytest.mark.asyncio
async def test_user_processor_upsert_event_calls_exporter() -> None:
    processor = OktaUserWebhookProcessor(event=WebhookEvent(trace_id="t", payload={}, headers={}))

    payload = {
        "data": {
            "events": [
                {
                    "eventType": "user.lifecycle.activate",
                    "target": [
                        {"type": "User", "id": "u1"},
                        {"type": "User", "id": "u2"},
                    ],
                }
            ]
        }
    }

    with patch("okta.webhook_processors.user_webhook_processor.OktaClientFactory.get_client") as get_client, patch(
        "okta.webhook_processors.user_webhook_processor.OktaUserExporter"
    ) as exporter_cls:
        mock_client = object()
        get_client.return_value = mock_client
        exporter = exporter_cls.return_value
        exporter.get_resource = AsyncMock(side_effect=[{"id": "u1"}, {"id": "u2"}])

        res = await processor.handle_event(payload, _resource_config())
        assert res.updated_raw_results == [{"id": "u1"}, {"id": "u2"}]
        assert res.deleted_raw_results == []
        assert exporter.get_resource.await_count == 2


