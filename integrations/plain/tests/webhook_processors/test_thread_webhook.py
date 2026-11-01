from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from integration import ThreadResourceConfig, ThreadSelector
from plain.utils import ObjectKind
from webhook_processors.thread_webhook_processor import ThreadWebhookProcessor


def _event(
    payload: dict[str, Any], headers: dict[str, str] | None = None
) -> WebhookEvent:
    event = WebhookEvent(
        trace_id="test",
        payload=payload,
        headers=headers or {},
    )
    event._original_request = MagicMock()
    event._original_request.body = AsyncMock(return_value=b"{}")
    return event


def _resource_config(*, exclude_done: bool = False) -> ThreadResourceConfig:
    return ThreadResourceConfig(
        kind=ObjectKind.THREAD,
        selector=ThreadSelector(query="true", excludeDoneThreads=exclude_done),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"plainThread"',
                    icon=None,
                    team=None,
                    properties={},
                )
            ),
            itemsToParse=None,
        ),
    )


@pytest.mark.asyncio
async def test_thread_webhook_upserts_via_get_thread() -> None:
    processor = ThreadWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_created",
                "payload": {"thread": {"id": "th_1"}},
            }
        )
    )
    with patch("webhook_processors.thread_webhook_processor.PlainClient") as client_cls:
        client = client_cls.return_value
        client.get_thread = AsyncMock(
            return_value={"id": "th_1", "status": "TODO", "title": "Help"}
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config()
        )

    assert result.updated_raw_results == [
        {"id": "th_1", "status": "TODO", "title": "Help"}
    ]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_thread_webhook_deletes_done_when_excluded() -> None:
    processor = ThreadWebhookProcessor(
        event=_event(
            {
                "type": "thread.thread_status_transitioned",
                "payload": {"thread": {"id": "th_1"}},
            }
        )
    )
    with patch("webhook_processors.thread_webhook_processor.PlainClient") as client_cls:
        client = client_cls.return_value
        client.get_thread = AsyncMock(
            return_value={"id": "th_1", "status": "DONE", "title": "Done"}
        )
        result = await processor.handle_event(
            processor.event.payload, _resource_config(exclude_done=True)
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {"id": "th_1", "status": "DONE", "title": "Done"}
    ]


@pytest.mark.asyncio
async def test_should_process_only_thread_events() -> None:
    processor = ThreadWebhookProcessor(
        event=_event({"type": "customer.customer_created", "payload": {}})
    )
    with patch(
        "webhook_processors.plain_abstract_webhook_processor.ocean"
    ) as mock_ocean:
        mock_ocean.integration_config = {}
        assert await processor.should_process_event(processor.event) is False

    processor.event = _event(
        {"type": "thread.thread_created", "payload": {"thread": {"id": "th_1"}}}
    )
    with patch(
        "webhook_processors.plain_abstract_webhook_processor.ocean"
    ) as mock_ocean:
        mock_ocean.integration_config = {}
        assert await processor.should_process_event(processor.event) is True
