import asyncio

import pytest

from port_ocean.context.event import EventType, _event_context_stack, event_context
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


@pytest.mark.asyncio
async def test_event_context_is_reset_when_the_body_raises() -> None:
    with pytest.raises(RuntimeError):
        async with event_context(EventType.ACTION_RUN, trigger_type="machine"):
            raise RuntimeError("execution failed before acknowledgement")

    assert _event_context_stack.top is None


@pytest.mark.asyncio
async def test_event_context_opens_after_a_failed_one_in_the_same_task() -> None:
    async def handle_two_runs() -> str:
        with pytest.raises(RuntimeError):
            async with event_context(EventType.ACTION_RUN, trigger_type="machine"):
                raise RuntimeError("execution failed before acknowledgement")

        async with event_context(
            EventType.ACTION_RUN, trigger_type="machine"
        ) as second_event:
            assert second_event.parent is None
            return second_event.id

    assert await asyncio.create_task(handle_two_runs())
    assert _event_context_stack.top is None


@pytest.mark.asyncio
async def test_nested_event_context_failure_restores_the_outer_context() -> None:
    async with event_context(EventType.RESYNC, trigger_type="machine") as outer_event:
        outer_event.port_app_config = PortAppConfig()
        outer_event_id = outer_event.id
        with pytest.raises(RuntimeError):
            async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
                raise RuntimeError("nested event failed")

        restored_event = _event_context_stack.top
        assert restored_event is not None
        assert restored_event.id == outer_event_id
        assert restored_event.event_type == EventType.RESYNC

    assert _event_context_stack.top is None
