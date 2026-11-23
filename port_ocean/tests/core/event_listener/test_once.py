import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.event_listener.once import (
    ONCE_EXIT_GRACE_SECONDS,
    OnceEventListener,
    OnceEventListenerSettings,
)


@pytest.mark.asyncio
async def test_once_listener_schedules_force_exit_after_resync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener = OnceEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=OnceEventListenerSettings(type="ONCE"),
    )
    monkeypatch.setattr(listener, "_resync", AsyncMock())

    mock_thread = MagicMock()
    raise_signal = MagicMock()

    with (
        patch(
            "port_ocean.core.event_listener.once.threading.Thread",
            return_value=mock_thread,
        ) as thread_cls,
        patch(
            "port_ocean.core.event_listener.once.signal.raise_signal",
            raise_signal,
        ),
        patch(
            "port_ocean.core.event_listener.once.ocean",
        ) as mock_ocean,
    ):
        mock_ocean.config.integration.incremental_sync_enabled = False
        await listener._start()
        # repeat_every schedules via ensure_future; wait for it to finish
        await asyncio.sleep(0.05)

    thread_cls.assert_called_once()
    kwargs = thread_cls.call_args.kwargs
    assert kwargs["daemon"] is True
    assert kwargs["name"] == "once-force-exit"
    assert ONCE_EXIT_GRACE_SECONDS > 0
    mock_thread.start.assert_called_once()
    raise_signal.assert_called_once()
