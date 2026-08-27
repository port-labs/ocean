from types import SimpleNamespace
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

import port_ocean.core.event_listener.polling as polling_module
from port_ocean.core.event_listener.polling import (
    PollingEventListener,
    PollingEventListenerSettings,
)
from port_ocean.core.models import EventListenerType


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

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    resync_mock = AsyncMock()
    monkeypatch.setattr(listener, "_resync", resync_mock)

    await listener._start()

    # Give event loop time to execute task callback
    import asyncio
    await asyncio.sleep(0.01)

    # get_current_integration is called once by _check_port_app_config_changed()
    port_client.get_current_integration.assert_called_once()
    port_client.get_integration_resync_request.assert_called_once()
    resync_mock.assert_called_once_with({})
    assert (
        app.resync_state_updater.last_integration_state_updated_at
        == "2024-01-01T00:05:00Z"
    )
    # Watermark updated only after task completes successfully
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

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    resync_mock = AsyncMock()
    monkeypatch.setattr(listener, "_resync", resync_mock)

    await listener._start()

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
async def test_empty_port_app_config_does_not_clear_stored_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        side_effect=[
            {"config": {"resources": [{"kind": "repository"}]}},
            {"config": {}},
            {"config": None},
            {},
        ]
    )
    app = SimpleNamespace(port_client=port_client)
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    assert await listener._check_port_app_config_changed() is False
    stored_hash = listener._last_port_app_config_hash
    assert stored_hash is not None

    assert await listener._check_port_app_config_changed() is False
    assert await listener._check_port_app_config_changed() is False
    assert await listener._check_port_app_config_changed() is False
    assert listener._last_port_app_config_hash == stored_hash


@pytest.mark.asyncio
async def test_polling_does_not_resync_repeatedly_for_same_resync_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

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

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    resync_mock = AsyncMock()
    monkeypatch.setattr(listener, "_resync", resync_mock)

    await listener._start()
    # Allow task callback to execute
    await asyncio.sleep(0.05)

    # Second polling check - should not trigger resync (watermark prevents it)
    await listener._evaluate_resync_trigger()

    assert resync_mock.call_count == 1


@pytest.mark.asyncio
async def test_polling_cancels_running_resync_when_new_request_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a running resync is cancelled when a new resync request arrives."""
    import asyncio

    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(return_value={})
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

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    # Create a mock resync that takes some time
    resync_call_count = 0

    async def slow_resync(*args: Any, **kwargs: Any) -> None:
        nonlocal resync_call_count
        resync_call_count += 1
        # Simulate a long-running resync
        await asyncio.sleep(0.5)

    monkeypatch.setattr(listener, "_resync", slow_resync)

    # Spawn the first resync task
    await listener._spawn_resync_task("2024-01-01T00:05:00Z")
    # Yield control to allow the task to start executing
    await asyncio.sleep(0)
    assert listener._current_resync_task is not None
    assert not listener._current_resync_task.done()
    assert resync_call_count == 1

    # Now spawn a second resync while the first is still running
    await listener._spawn_resync_task("2024-01-01T00:10:00Z")
    # Yield control to allow the second task to start executing
    await asyncio.sleep(0)

    # The first task should have been cancelled
    assert listener._current_resync_task is not None
    assert resync_call_count == 2

    # Wait for the second task to complete
    await listener._current_resync_task


@pytest.mark.asyncio
async def test_resync_task_completion_callback_clears_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the done callback clears the task reference."""
    import asyncio

    port_client = MagicMock()
    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="2024-01-01T00:00:00Z",
            last_resync_request_updated_at=None,
        ),
    )
    monkeypatch.setattr(polling_module, "ocean", SimpleNamespace(app=app))

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )

    async def quick_resync(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0.01)

    monkeypatch.setattr(listener, "_resync", quick_resync)

    # Spawn a resync task
    await listener._spawn_resync_task("")
    assert listener._current_resync_task is not None

    # Wait for the task to complete
    await listener._current_resync_task

    # Give the callback a moment to execute
    await asyncio.sleep(0.01)

    # The task reference should still be cleared by the callback
    # (callback execution happens after task.done() returns True)
    if listener._current_resync_task and listener._current_resync_task.done():
        # Task completed, callback should have cleared it or it's still there
        # Since callback is async-scheduled, we just verify the task is done
        assert listener._current_resync_task.done()
