from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from plain.utils import ObjectKind
from webhook_processors.customer_webhook_processor import CustomerWebhookProcessor


def _event(payload: dict[str, Any]) -> WebhookEvent:
    event = WebhookEvent(trace_id="test", payload=payload, headers={})
    event._original_request = MagicMock()
    event._original_request.body = AsyncMock(return_value=b"{}")
    return event


def _resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.CUSTOMER,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".fullName",
                    blueprint='"plainCustomer"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )


@pytest.mark.asyncio
async def test_customer_upsert() -> None:
    processor = CustomerWebhookProcessor(
        event=_event(
            {
                "type": "customer.customer_updated",
                "payload": {"customer": {"id": "c_1"}},
            }
        )
    )
    with patch(
        "webhook_processors.customer_webhook_processor.PlainClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_customer = AsyncMock(return_value={"id": "c_1", "fullName": "Ada"})
        result = await processor.handle_event(
            processor.event.payload, _resource_config()
        )

    assert result.updated_raw_results == [{"id": "c_1", "fullName": "Ada"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_customer_delete() -> None:
    processor = CustomerWebhookProcessor(
        event=_event(
            {
                "type": "customer.customer_deleted",
                "payload": {"previousCustomer": {"id": "c_1"}},
            }
        )
    )
    result = await processor.handle_event(processor.event.payload, _resource_config())
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "c_1"}]
