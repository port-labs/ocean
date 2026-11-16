from unittest.mock import MagicMock, patch

from azure_integration.foundry.helpers.invoke_mode import (
    foundry_webhook_completion_available,
    invoke_agent_completion_mode,
)


def test_foundry_webhook_completion_available_requires_base_url() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = ""
    mock_ocean.app.config.event_listener.should_process_webhooks = True
    with patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean):
        assert foundry_webhook_completion_available() is False


def test_foundry_webhook_completion_available_ok() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = "https://ocean.example"
    mock_ocean.app.config.event_listener.should_process_webhooks = True
    with patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean):
        assert foundry_webhook_completion_available() is True


def test_invoke_agent_completion_mode_report_false() -> None:
    await_webhook, complete_on_sse = invoke_agent_completion_mode(
        report_invocation_status=False
    )
    assert await_webhook is False
    assert complete_on_sse is False


def test_invoke_agent_completion_mode_without_webhook() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = ""
    mock_ocean.app.config.event_listener.should_process_webhooks = False
    with patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean):
        await_webhook, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert await_webhook is False
    assert complete_on_sse is True


def test_invoke_agent_completion_mode_with_webhook() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = "https://ocean.example"
    mock_ocean.app.config.event_listener.should_process_webhooks = True
    with patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean):
        await_webhook, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert await_webhook is True
    assert complete_on_sse is False
