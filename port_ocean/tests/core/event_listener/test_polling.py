import asyncio
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import port_ocean.core.event_listener.polling as polling_module
from port_ocean.core.event_listener.polling import (
    PollingEventListener,
    PollingEventListenerSettings,
)
from port_ocean.core.models import EventListenerType
from port_ocean.utils.misc import IntegrationStateStatus


def _run_repeat_every_times(
    repetitions: int,
) -> Callable[
    ..., Callable[[Callable[[], Awaitable[None]]], Callable[[], Awaitable[None]]]
]:
    def mock_repeat_every(
        *_args: Any, **_kwargs: Any
    ) -> Callable[[Callable[[], Awaitable[None]]], Callable[[], Awaitable[None]]]:
        def decorator(
            func: Callable[[], Awaitable[None]],
        ) -> Callable[[], Awaitable[None]]:
            async def wrapped() -> None:
                for _ in range(repetitions):
                    await func()
                    await asyncio.sleep(0)

            return wrapped

        return decorator

    return mock_repeat_every


@pytest.mark.asyncio
async def test_polling_resyncs_from_resync_requests_when_integration_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:00:00Z"}
    )
    port_client.get_integration_resync_request = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "2024-01-01T00:05:00Z"}
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:00:00Z",
            last_resync_request_updated_at=None,
        ),
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))
    monkeypatch.setattr(polling_module, "repeat_every", _run_repeat_every_times(1))
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    resync_mock = AsyncMock()
    monkeypatch.setattr(listener, "_resync", resync_mock)

    await listener._start()
    await asyncio.sleep(0)

    port_client.get_current_integration.assert_not_called()
    port_client.get_integration_resync_request.assert_called_once()
    resync_mock.assert_called_once_with({})
    assert (
        app.resync_state_updater.last_integration_state_updated_at
        == "2024-01-01T00:05:00Z"
    )
    assert (
        app.resync_state_updater.last_resync_request_updated_at
        == "2024-01-01T00:05:00Z"
    )


@pytest.mark.asyncio
async def test_polling_resyncs_on_integration_change_with_resync_request_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:05:00Z"}
    )
    port_client.get_integration_resync_request = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "2024-01-01T00:05:00Z"}
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:00:00Z",
            last_resync_request_updated_at=None,
        ),
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))
    monkeypatch.setattr(polling_module, "repeat_every", _run_repeat_every_times(1))
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    resync_mock = AsyncMock()
    monkeypatch.setattr(listener, "_resync", resync_mock)

    await listener._start()
    await asyncio.sleep(0)

    port_client.get_integration_resync_request.assert_called_once()
    resync_mock.assert_called_once_with({})


def test_should_not_resync_when_resync_request_timestamp_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = SimpleNamespace(
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:00:00Z",
            last_resync_request_updated_at=None,
        )
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    assert listener.should_resync_from_resync_request("") is False
    assert listener.should_resync_from_resync_request(None) is False


def test_should_not_resync_when_resync_request_timestamp_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = SimpleNamespace(
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:00:00Z",
            last_resync_request_updated_at=None,
        )
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    assert listener.should_resync_from_resync_request("not-a-timestamp") is False


def test_should_not_resync_old_request_when_request_watermark_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = SimpleNamespace(
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:10:00Z",
            last_resync_request_updated_at=None,
        )
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    assert listener.should_resync_from_resync_request("2024-01-01T00:05:00Z") is False


@pytest.mark.asyncio
async def test_polling_does_not_resync_repeatedly_for_same_resync_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:00:00Z"}
    )
    port_client.get_integration_resync_request = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "2024-01-01T00:05:00Z"}
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:00:00Z",
            last_resync_request_updated_at=None,
        ),
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))
    monkeypatch.setattr(polling_module, "repeat_every", _run_repeat_every_times(2))
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    resync_mock = AsyncMock()
    monkeypatch.setattr(listener, "_resync", resync_mock)

    await listener._start()
    await asyncio.sleep(0)

    assert resync_mock.call_count == 1


@pytest.mark.asyncio
async def test_polling_cancels_current_resync_when_new_request_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that when a new resync request arrives while a resync is running,
    the current resync is cancelled and a new one starts with the updated timestamp.
    """
    port_client = MagicMock()

    # First call returns initial resync request, second call returns new request
    port_client.get_integration_resync_request = AsyncMock(
        side_effect=[
            {"id": "resync-1", "updatedAt": "2024-01-01T00:05:00Z"},
            {"id": "resync-2", "updatedAt": "2024-01-01T00:10:00Z"},  # New request
        ]
    )

    resync_state_updater = SimpleNamespace(
        last_integration_state_updated_at="2024-01-01T00:00:00Z",
        last_resync_request_updated_at=None,
        update_before_resync=AsyncMock(),
        update_after_resync=AsyncMock(),
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=resync_state_updater,
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    # Also need to patch ocean in base module for CancelledError handling
    import port_ocean.core.event_listener.base as base_module
    monkeypatch.setattr(base_module, "ocean", SimpleNamespace(app=app))

    monkeypatch.setattr(polling_module, "repeat_every", _run_repeat_every_times(2))
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    resync_calls: list[Any] = []
    second_resync_finished = asyncio.Event()

    async def resync_handler(args: Any) -> bool:
        resync_calls.append(args)
        if len(resync_calls) == 1:
            await asyncio.sleep(3600)
        else:
            second_resync_finished.set()
        return True

    listener = PollingEventListener(
        events={"on_resync": resync_handler},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    await listener._start()

    await asyncio.wait_for(second_resync_finished.wait(), timeout=1)
    for _ in range(100):
        if listener._current_resync_task is None:
            break
        await asyncio.sleep(0)
    else:
        pytest.fail("Resync task did not complete")

    # Verify get_integration_resync_request was called twice (once per iteration)
    assert port_client.get_integration_resync_request.call_count == 2

    # Verify watermark was updated to the new request timestamp
    assert (
        app.resync_state_updater.last_resync_request_updated_at
        == "2024-01-01T00:10:00Z"
    )

    # Verify current task is cleared after all resyncs complete
    assert listener._current_resync_task is None

    assert len(resync_calls) == 2
    aborted_status_updates = [
        call
        for call in resync_state_updater.update_after_resync.call_args_list
        if call.args and call.args[0] == IntegrationStateStatus.Aborted
    ]
    assert aborted_status_updates == []


@pytest.mark.asyncio
async def test_polling_logs_background_resync_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_integration_resync_request = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "2024-01-01T00:05:00Z"}
    )

    resync_state_updater = SimpleNamespace(
        last_integration_state_updated_at="2024-01-01T00:00:00Z",
        last_resync_request_updated_at=None,
        supersede_in_progress=False,
        update_before_resync=AsyncMock(),
        update_after_resync=AsyncMock(),
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=resync_state_updater,
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    import port_ocean.core.event_listener.base as base_module

    monkeypatch.setattr(base_module, "ocean", SimpleNamespace(app=app))
    monkeypatch.setattr(polling_module, "repeat_every", _run_repeat_every_times(1))
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    async def failing_resync(_args: Any) -> bool:
        raise RuntimeError("sync failed")

    listener = PollingEventListener(
        events={"on_resync": failing_resync},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    bound_logger = MagicMock()
    with patch.object(polling_module.logger, "bind", return_value=bound_logger):
        await listener._start()
        for _ in range(100):
            if listener._current_resync_task is None:
                break
            await asyncio.sleep(0)
        else:
            pytest.fail("Resync task did not complete")

    bound_logger.error.assert_called_once()
    assert "Resync task failed: sync failed" in bound_logger.error.call_args.args[0]
    assert resync_state_updater.update_after_resync.call_args_list[-1].args[0] == (
        IntegrationStateStatus.Failed
    )
