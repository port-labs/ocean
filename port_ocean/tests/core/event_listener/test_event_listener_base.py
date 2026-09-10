from unittest.mock import AsyncMock

import pytest

from port_ocean.core.event_listener.base import BaseEventListener
from port_ocean.exceptions.api import EmptyPortAppConfigError


class _TestEventListener(BaseEventListener):
    async def _start(self) -> None:
        pass


@pytest.mark.asyncio
async def test_resync_calls_after_resync_when_on_resync_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener = _TestEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
    )
    before_resync = AsyncMock()
    after_resync = AsyncMock()
    on_resync_failure = AsyncMock()
    monkeypatch.setattr(listener, "_before_resync", before_resync)
    monkeypatch.setattr(listener, "_after_resync", after_resync)
    monkeypatch.setattr(listener, "_on_resync_failure", on_resync_failure)

    await listener._resync({})

    before_resync.assert_awaited_once()
    after_resync.assert_awaited_once()
    on_resync_failure.assert_not_awaited()


@pytest.mark.asyncio
async def test_resync_fails_when_port_app_config_cannot_be_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener = _TestEventListener(
        events={
            "on_resync": AsyncMock(side_effect=EmptyPortAppConfigError()),
        }
    )
    before_resync = AsyncMock()
    after_resync = AsyncMock()
    on_resync_failure = AsyncMock()
    monkeypatch.setattr(listener, "_before_resync", before_resync)
    monkeypatch.setattr(listener, "_after_resync", after_resync)
    monkeypatch.setattr(listener, "_on_resync_failure", on_resync_failure)

    with pytest.raises(EmptyPortAppConfigError):
        await listener._resync({})

    before_resync.assert_awaited_once()
    after_resync.assert_not_awaited()
    on_resync_failure.assert_awaited_once()
