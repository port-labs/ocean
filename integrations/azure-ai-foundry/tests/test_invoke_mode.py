from unittest.mock import MagicMock, patch

import pytest

from helpers.invoke_mode import (
    foundry_webhook_completion_available,
    invoke_agent_completion_mode,
)


@pytest.mark.parametrize(
    ("base_url", "webhooks", "secret", "expected"),
    [
        ("https://ocean.example", True, "sec", True),
        ("", True, "sec", False),
        ("https://ocean.example", False, "sec", False),
        ("https://ocean.example", True, "", False),
    ],
)
def test_foundry_webhook_completion_available(
    base_url: str, webhooks: bool, secret: str, expected: bool
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = base_url
    mock_ocean.app.config.event_listener.should_process_webhooks = webhooks
    mock_ocean.integration_config = {"webhookSigningSecret": secret}
    with patch("helpers.invoke_mode.ocean", mock_ocean):
        assert foundry_webhook_completion_available() is expected


def test_invoke_agent_completion_mode_without_webhook() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = ""
    mock_ocean.app.config.event_listener.should_process_webhooks = False
    mock_ocean.integration_config = {}
    with patch("helpers.invoke_mode.ocean", mock_ocean):
        use_background, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert use_background is False
    assert complete_on_sse is True


def test_invoke_agent_completion_mode_with_webhook() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = "https://ocean.example"
    mock_ocean.app.config.event_listener.should_process_webhooks = True
    mock_ocean.integration_config = {"webhookSigningSecret": "x"}
    with patch("helpers.invoke_mode.ocean", mock_ocean):
        use_background, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert use_background is True
    assert complete_on_sse is False
