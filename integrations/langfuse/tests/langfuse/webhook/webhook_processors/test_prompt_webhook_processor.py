from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from langfuse.helpers.utils import ObjectKind
from langfuse.webhook.webhook_processors.prompt_webhook_processor import (
    PromptWebhookProcessor,
)


def _event(payload: dict[str, object]) -> WebhookEvent:
    return WebhookEvent(trace_id="test", payload=payload, headers={})


@pytest.fixture
def created_event() -> WebhookEvent:
    return _event(
        {
            "id": "evt-1",
            "type": "prompt-version",
            "action": "created",
            "prompt": {"id": "p1", "name": "movie-critic", "version": 3},
        }
    )


@pytest.mark.asyncio
class TestPromptWebhookProcessor:
    async def test_should_process_event(self, created_event: WebhookEvent) -> None:
        processor = PromptWebhookProcessor(event=created_event)
        assert await processor.should_process_event(created_event) is True

    async def test_get_matching_kinds(self, created_event: WebhookEvent) -> None:
        processor = PromptWebhookProcessor(event=created_event)
        assert await processor.get_matching_kinds(created_event) == [ObjectKind.PROMPT]

    async def test_validate_payload(self, created_event: WebhookEvent) -> None:
        processor = PromptWebhookProcessor(event=created_event)
        assert await processor.validate_payload(created_event.payload) is True

    async def test_validate_payload_missing_prompt(self) -> None:
        event = _event({"type": "prompt-version", "action": "created"})
        processor = PromptWebhookProcessor(event=event)
        assert await processor.validate_payload(event.payload) is False

    async def test_handle_created_upserts(self, created_event: WebhookEvent) -> None:
        meta = {
            "name": "movie-critic",
            "type": "text",
            "versions": [3],
            "labels": ["production"],
            "tags": [],
            "lastUpdatedAt": "2024-07-10T10:30:00Z",
            "lastConfig": {},
        }
        processor = PromptWebhookProcessor(event=created_event)
        with (
            patch(
                "langfuse.webhook.webhook_processors.prompt_webhook_processor.create_langfuse_client",
                return_value=MagicMock(),
            ),
            patch(
                "langfuse.webhook.webhook_processors.prompt_webhook_processor.PromptExporter"
            ) as exporter_cls,
        ):
            exporter_cls.return_value.get_resource = AsyncMock(return_value=meta)
            result = await processor.handle_event(created_event.payload, MagicMock())
        assert result.updated_raw_results == [meta]
        assert result.deleted_raw_results == []

    async def test_handle_deleted_when_gone(self) -> None:
        event = _event(
            {
                "type": "prompt-version",
                "action": "deleted",
                "prompt": {"name": "gone-prompt", "version": 1},
            }
        )
        processor = PromptWebhookProcessor(event=event)
        with (
            patch(
                "langfuse.webhook.webhook_processors.prompt_webhook_processor.create_langfuse_client",
                return_value=MagicMock(),
            ),
            patch(
                "langfuse.webhook.webhook_processors.prompt_webhook_processor.PromptExporter"
            ) as exporter_cls,
        ):
            exporter_cls.return_value.get_resource = AsyncMock(return_value=None)
            result = await processor.handle_event(event.payload, MagicMock())
        assert result.deleted_raw_results == [{"name": "gone-prompt"}]
        assert result.updated_raw_results == []
