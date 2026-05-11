from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import port_ocean.core.event_listener.polling as polling_module
from port_ocean.core.event_listener.polling import (
    PollingEventListener,
    PollingEventListenerSettings,
)
from port_ocean.core.models import EventListenerType, IntegrationFeatureFlag


def _run_once_repeat_every(*_args, **_kwargs):
    def decorator(func):
        async def wrapped():
            await func()

        return wrapped

    return decorator


def _run_twice_repeat_every(*_args, **_kwargs):
    def decorator(func):
        async def wrapped():
            await func()
            await func()

        return wrapped

    return decorator


@pytest.mark.asyncio
async def test_polling_resyncs_from_resync_requests_when_feature_flag_enabled(
    monkeypatch,
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
    port_client.get_integration_resync_requests = AsyncMock(
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
    monkeypatch.setattr(polling_module, "repeat_every", _run_once_repeat_every)
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    listener._resync = AsyncMock()

    await listener._start()

    port_client.get_current_integration.assert_called_once_with(is_polling=True)
    port_client.get_integration_resync_requests.assert_called_once()
    listener._resync.assert_called_once_with({})
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
    monkeypatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "2024-01-01T00:00:00Z"}
    )
    port_client.get_organization_feature_flags = AsyncMock(return_value=[])
    port_client.get_integration_resync_requests = AsyncMock(
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
    monkeypatch.setattr(polling_module, "repeat_every", _run_once_repeat_every)
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    listener._resync = AsyncMock()

    await listener._start()

    port_client.get_integration_resync_requests.assert_not_called()
    listener._resync.assert_not_called()


@pytest.mark.asyncio
async def test_polling_resyncs_on_integration_change_without_resync_requests_lookup(
    monkeypatch,
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
    port_client.get_integration_resync_requests = AsyncMock(
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
    monkeypatch.setattr(polling_module, "repeat_every", _run_once_repeat_every)
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    listener._resync = AsyncMock()

    await listener._start()

    port_client.get_organization_feature_flags.assert_not_called()
    port_client.get_integration_resync_requests.assert_not_called()
    listener._resync.assert_called_once_with({})


def test_should_not_resync_when_resync_request_timestamp_is_missing(
    monkeypatch,
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


def test_should_not_resync_when_resync_request_timestamp_is_invalid(
    monkeypatch,
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
    monkeypatch,
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
    port_client.get_integration_resync_requests = AsyncMock(
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
    monkeypatch.setattr(polling_module, "repeat_every", _run_twice_repeat_every)
    monkeypatch.setattr(
        polling_module, "signal_handler", SimpleNamespace(register=lambda *_: None)
    )

    listener = PollingEventListener(
        events={"on_resync": AsyncMock(return_value=True)},
        event_listener_config=PollingEventListenerSettings(
            type=EventListenerType.POLLING
        ),
    )
    listener._resync = AsyncMock()

    await listener._start()

    assert listener._resync.call_count == 1
