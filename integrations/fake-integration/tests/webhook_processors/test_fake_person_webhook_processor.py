from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from integration import ObjectKind
from webhook_processors.constants import FAKE_TASK_COMPLETED_EVENT
from webhook_processors.fake_person_webhook_processor import FakePersonWebhookProcessor


def make_event(payload: dict[str, object]) -> WebhookEvent:
    return WebhookEvent(
        trace_id="trace-1",
        payload=payload,
        headers={},
    )


@pytest.mark.asyncio
class TestFakePersonWebhookProcessor:
    async def test_get_matching_kinds(self) -> None:
        event = make_event({})
        processor = FakePersonWebhookProcessor(event)

        assert await processor.get_matching_kinds(event) == [ObjectKind.PERSON]

    async def test_should_process_event_skips_fake_task_completed(self) -> None:
        event = make_event({"event": FAKE_TASK_COMPLETED_EVENT})
        processor = FakePersonWebhookProcessor(event)

        assert await processor.should_process_event(event) is False

    async def test_should_process_event_processes_other_events(self) -> None:
        event = make_event({"event": "some.other.event"})
        processor = FakePersonWebhookProcessor(event)

        assert await processor.should_process_event(event) is True

    async def test_handle_event_registers_random_person(self) -> None:
        person = {"id": "person-1", "name": "Test Person"}
        event = make_event({})
        processor = FakePersonWebhookProcessor(event)

        with (
            patch(
                "webhook_processors.fake_person_webhook_processor.get_random_person_from_batch",
                new=AsyncMock(return_value=person),
            ),
            patch(
                "webhook_processors.fake_person_webhook_processor.ocean"
            ) as mock_ocean,
        ):
            mock_ocean.register_raw = AsyncMock()
            result = await processor.handle_event(
                event.payload, MagicMock(spec=ResourceConfig)
            )

        mock_ocean.register_raw.assert_awaited_once_with(ObjectKind.PERSON, [person])
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
