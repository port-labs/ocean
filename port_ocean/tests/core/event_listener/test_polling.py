from types import SimpleNamespace
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

import port_ocean.core.event_listener.polling as polling_module
from port_ocean.core.event_listener.polling import (
    PollingEventListener,
    PollingEventListenerSettings,
)
from port_ocean.core.models import EventListenerType, IntegrationFeatureFlag


def _run_repeat_every_times(
    repetitions: int,
) -> Callable[
    ..., Callable[[Callable[[], Awaitable[None]]], Callable[[], Awaitable[None]]]
]:
    def mock_repeat_every(
        *_args: Any, **_kwargs: Any
    ) -> Callable[[Callable[[], Awaitable[None]]], Callable[[], Awaitable[None]]]:
        def decorator(
            func: Callable[[], Awaitable[None]]
        ) -> Callable[[], Awaitable[None]]:
            async def wrapped() -> None:
                for _ in range(repetitions):
                    await func()

            return wrapped

        return decorator

    return mock_repeat_every


@pytest.mark.asyncio
async def test_polling_resyncs_from_resync_requests_when_feature_flag_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:00:00Z"}
    )
    port_client.get_organization_feature_flags = AsyncMock(
        return_value=[
            IntegrationFeatureFlag.OCEAN_POLLING_INTEGRATION_RESYNC_REQUESTS_ENABLED
        ]
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

    port_client.get_current_integration.assert_called_once_with(is_polling=True)
    port_client.get_integration_resync_request.assert_called_once()
    resync_mock.assert_called_once_with({})
    assert (
        app.resync_state_updater.last_integration_state_updated_at
        == "2024-01-01T00:00:00Z"
    )
    assert (
        app.resync_state_updater.last_resync_request_updated_at
        == "2024-01-01T00:05:00Z"
    )


@pytest.mark.asyncio
async def test_polling_does_not_fetch_resync_requests_when_feature_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:00:00Z"}
    )
    port_client.get_organization_feature_flags = AsyncMock(return_value=[])
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

    port_client.get_integration_resync_request.assert_not_called()
    resync_mock.assert_not_called()


@pytest.mark.asyncio
async def test_polling_resyncs_on_integration_change_without_resync_requests_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:05:00Z"}
    )
    port_client.get_organization_feature_flags = AsyncMock(
        return_value=[
            IntegrationFeatureFlag.OCEAN_POLLING_INTEGRATION_RESYNC_REQUESTS_ENABLED
        ]
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

    port_client.get_organization_feature_flags.assert_not_called()
    port_client.get_integration_resync_request.assert_not_called()
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


@pytest.mark.asyncio
async def test_polling_does_not_resync_repeatedly_for_same_resync_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:00:00Z"}
    )
    port_client.get_organization_feature_flags = AsyncMock(
        return_value=[
            IntegrationFeatureFlag.OCEAN_POLLING_INTEGRATION_RESYNC_REQUESTS_ENABLED
        ]
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

    assert resync_mock.call_count == 1
