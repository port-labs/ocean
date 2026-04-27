import pytest
from unittest.mock import AsyncMock, patch
from typing import Any
from port_ocean.context.ocean import ocean


def _get_on_start_fn() -> Any:
    """Extract the real on_start async function registered via @ocean.on_start().

    The decorator calls ocean.app.integration.on_start(fn) which, in test context,
    is a MagicMock. The original function is captured in the mock's call history.
    """
    return ocean.app.integration.on_start.call_args.args[0]  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestSkipWebhookManagement:
    async def test_on_start_skips_webhook_creation_when_flag_enabled(
        self, mock_ocean_context: Any
    ) -> None:
        ocean.integration_config["skip_webhook_management"] = True
        ocean.app.config.event_listener.should_process_webhooks = True

        mock_create = AsyncMock()
        with patch("main._create_webhooks_for_organization", mock_create):
            import main  # noqa: F401 — triggers @ocean.on_start() registration

            await _get_on_start_fn()()

        mock_create.assert_not_called()
        ocean.integration_config.pop("skip_webhook_management", None)

    async def test_on_start_proceeds_when_flag_not_set(
        self, mock_ocean_context: Any
    ) -> None:
        ocean.integration_config.pop("skip_webhook_management", None)
        ocean.app.config.event_listener.should_process_webhooks = True

        mock_create = AsyncMock()
        with patch("main._create_webhooks_for_organization", mock_create):
            import main  # noqa: F401

            await _get_on_start_fn()()

        mock_create.assert_called_once()
