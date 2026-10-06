from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main import on_start
from plain.constants import WEBHOOK_EVENT_TYPES, WEBHOOK_PATH_SUFFIX
from tests.kind_helpers import make_client


@pytest.mark.parametrize("raw", [False, "false", None])
async def test_on_start_skips_registration_when_disabled(
    raw: bool | str | None,
) -> None:
    from port_ocean.context.ocean import ocean

    original = ocean.app.config.integration.config
    config: dict[str, Any] = {"api_token": "plainApiKey_test"}
    if raw is not None:
        config["enable_live_events"] = raw
    ocean.app.config.integration.config = config
    try:
        with patch("main.register_webhook_target", new_callable=AsyncMock) as register:
            await on_start()
        register.assert_not_awaited()
    finally:
        ocean.app.config.integration.config = original


async def test_on_start_registers_when_enabled() -> None:
    from port_ocean.context.ocean import ocean

    original = ocean.app.config.integration.config
    original_listener = ocean.app.config.event_listener.type
    ocean.app.config.integration.config = {
        "api_token": "plainApiKey_test",
        "enable_live_events": True,
    }
    ocean.app.config.event_listener.type = "POLLING"  # type: ignore[assignment]
    try:
        with patch("main.register_webhook_target", new_callable=AsyncMock) as register:
            await on_start()
        register.assert_awaited_once()
    finally:
        ocean.app.config.integration.config = original
        ocean.app.config.event_listener.type = original_listener


async def test_register_webhook_target_does_not_fail_without_permissions() -> None:
    from port_ocean.exceptions.core import OceanAbortException

    mock_ocean = MagicMock()
    mock_ocean.app.base_url = "https://example.com"
    client = MagicMock()
    client.ensure_webhook_target = AsyncMock(
        side_effect=OceanAbortException(
            'The Plain API key is missing the "webhookTarget:create" permission'
        )
    )

    with (
        patch("plain.webhook_setup.ocean", mock_ocean),
        patch("plain.webhook_setup.PlainClient", return_value=client),
        patch("plain.webhook_setup.logger") as log,
    ):
        from plain.webhook_setup import register_webhook_target

        await register_webhook_target()

    log.warning.assert_called_once()
    message = log.warning.call_args.args[0]
    assert "manually" in message
    assert log.warning.call_args.args[2] == f"https://example.com{WEBHOOK_PATH_SUFFIX}"


async def test_ensure_webhook_target_creates_when_missing() -> None:
    client = make_client()
    client.paginate_connection = MagicMock(  # type: ignore[method-assign]
        return_value=_empty_async_gen()
    )
    client.execute = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "createWebhookTarget": {
                "webhookTarget": {
                    "id": "wh_1",
                    "url": "https://example.com/integration/webhook",
                },
                "error": None,
            }
        }
    )

    with patch("plain.client.ocean") as mock_ocean:
        mock_ocean.config.integration.identifier = "plain"
        await client.ensure_webhook_target("https://example.com")

    assert client.execute.await_count == 1
    args = client.execute.await_args
    assert args is not None
    variables = args.args[1]
    assert variables["input"]["url"] == f"https://example.com{WEBHOOK_PATH_SUFFIX}"
    assert {item["eventType"] for item in variables["input"]["eventSubscriptions"]} == (
        set(WEBHOOK_EVENT_TYPES)
    )


async def test_ensure_webhook_target_updates_existing() -> None:
    client = make_client()

    async def existing_targets(*_args: Any, **_kwargs: Any) -> Any:
        yield [
            {
                "id": "wh_1",
                "url": f"https://example.com{WEBHOOK_PATH_SUFFIX}",
                "description": "plain-Port-Ocean-Events-Webhook",
            }
        ]

    client.paginate_connection = existing_targets  # type: ignore[method-assign]
    client.execute = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "updateWebhookTarget": {
                "webhookTarget": {"id": "wh_1"},
                "error": None,
            }
        }
    )

    with patch("plain.client.ocean") as mock_ocean:
        mock_ocean.config.integration.identifier = "plain"
        await client.ensure_webhook_target("https://example.com")

    assert client.execute.await_count == 1
    args = client.execute.await_args
    assert args is not None
    assert args.args[1]["input"]["webhookTargetId"] == "wh_1"


async def _empty_async_gen() -> Any:
    if False:
        yield []
