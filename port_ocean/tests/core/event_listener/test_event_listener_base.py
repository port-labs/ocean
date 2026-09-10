import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from port_ocean.context.event import EventType, event, event_context
from port_ocean.core.event_listener.base import BaseEventListener
from port_ocean.utils.misc import IntegrationStateStatus


class _TestEventListener(BaseEventListener):
    async def _start(self) -> None:
        pass


@pytest.fixture
def resync_state_updater() -> SimpleNamespace:
    return SimpleNamespace(
        supersede_in_progress=False,
        update_before_resync=AsyncMock(),
        update_after_resync=AsyncMock(),
    )


@pytest.fixture
def listener(
    monkeypatch: pytest.MonkeyPatch, resync_state_updater: SimpleNamespace
) -> _TestEventListener:
    app = SimpleNamespace(resync_state_updater=resync_state_updater)
    monkeypatch.setattr(
        "port_ocean.core.event_listener.base.ocean", SimpleNamespace(app=app)
    )
    return _TestEventListener(events={"on_resync": AsyncMock(return_value=True)})


@pytest.mark.asyncio
async def test_resync_marks_aborted_on_cancel(
    listener: _TestEventListener, resync_state_updater: SimpleNamespace
) -> None:
    async def cancelled_resync(_args: object) -> bool:
        raise asyncio.CancelledError

    listener.events["on_resync"] = cancelled_resync

    with pytest.raises(asyncio.CancelledError):
        await listener._resync({})

    resync_state_updater.update_after_resync.assert_awaited_once_with(
        IntegrationStateStatus.Aborted
    )


@pytest.mark.asyncio
async def test_resync_skips_aborted_when_supersede_in_progress(
    listener: _TestEventListener, resync_state_updater: SimpleNamespace
) -> None:
    resync_state_updater.supersede_in_progress = True

    async def cancelled_resync(_args: object) -> bool:
        raise asyncio.CancelledError

    listener.events["on_resync"] = cancelled_resync

    with pytest.raises(asyncio.CancelledError):
        await listener._resync({})

    resync_state_updater.update_after_resync.assert_not_awaited()


@pytest.mark.asyncio
async def test_resync_skips_aborted_when_superseded_by_newer_resync_event(
    listener: _TestEventListener, resync_state_updater: SimpleNamespace
) -> None:
    async def cancelled_resync(_args: object) -> bool:
        event.abort()
        raise asyncio.CancelledError

    listener.events["on_resync"] = cancelled_resync

    async with event_context(EventType.RESYNC, trigger_type="machine"):
        with pytest.raises(asyncio.CancelledError):
            await listener._resync({})

    resync_state_updater.update_after_resync.assert_not_awaited()


@pytest.mark.asyncio
async def test_resync_marks_aborted_when_externally_aborted(
    listener: _TestEventListener, resync_state_updater: SimpleNamespace
) -> None:
    async def externally_cancelled_resync(_args: object) -> bool:
        event.abort(external_abort=True)
        raise asyncio.CancelledError

    listener.events["on_resync"] = externally_cancelled_resync

    async with event_context(EventType.RESYNC, trigger_type="machine"):
        with pytest.raises(asyncio.CancelledError):
            await listener._resync({})

    resync_state_updater.update_after_resync.assert_awaited_once_with(
        IntegrationStateStatus.Aborted
    )
