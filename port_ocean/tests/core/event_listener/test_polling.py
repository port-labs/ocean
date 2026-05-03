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


@pytest.mark.asyncio
async def test_polling_resyncs_from_resync_requests_when_feature_flag_enabled(
    monkeypatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "same-update"}
    )
    port_client.get_organization_feature_flags = AsyncMock(
        return_value=[
            IntegrationFeatureFlag.OCEAN_POLLING_INTEGRATION_RESYNC_REQUESTS_ENABLED
        ]
    )
    port_client.get_integration_resync_requests = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "new-update"}
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="same-update"
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


@pytest.mark.asyncio
async def test_polling_does_not_fetch_resync_requests_when_feature_flag_disabled(
    monkeypatch,
) -> None:
    port_client = MagicMock()
    port_client.get_current_integration = AsyncMock(
        return_value={"updatedAt": "same-update"}
    )
    port_client.get_organization_feature_flags = AsyncMock(return_value=[])
    port_client.get_integration_resync_requests = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "new-update"}
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="same-update"
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
        return_value={"updatedAt": "new-update"}
    )
    port_client.get_organization_feature_flags = AsyncMock(
        return_value=[
            IntegrationFeatureFlag.OCEAN_POLLING_INTEGRATION_RESYNC_REQUESTS_ENABLED
        ]
    )
    port_client.get_integration_resync_requests = AsyncMock(
        return_value={"id": "resync-1", "updatedAt": "new-update"}
    )

    app = SimpleNamespace(
        port_client=port_client,
        resync_state_updater=SimpleNamespace(
            last_integration_state_updated_at="old-update"
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
