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


def test_invoke_agent_completion_mode_without_webhook() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = ""
    mock_ocean.app.config.event_listener.should_process_webhooks = False
    with patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean):
        use_background, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert use_background is False
    assert complete_on_sse is True


def test_invoke_agent_completion_mode_with_signing_secret() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = "https://ocean.example"
    mock_ocean.app.config.event_listener.should_process_webhooks = True
    with (
        patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_mode.has_any_signing_secret",
            return_value=True,
        ),
    ):
        use_background, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert use_background is True
    assert complete_on_sse is False


def test_invoke_agent_completion_mode_sse_fallback_without_secret() -> None:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = "https://ocean.example"
    mock_ocean.app.config.event_listener.should_process_webhooks = True
    with (
        patch("azure_integration.foundry.helpers.invoke_mode.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_mode.has_any_signing_secret",
            return_value=False,
        ),
    ):
        use_background, complete_on_sse = invoke_agent_completion_mode(
            report_invocation_status=True
        )
    assert use_background is False
    assert complete_on_sse is True
