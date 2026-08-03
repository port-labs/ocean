from unittest.mock import MagicMock, patch

from clients.claude_client import ClaudeDeployment
from clients.client_factory import is_deployment_enabled


def _client(deployment: ClaudeDeployment) -> MagicMock:
    client = MagicMock()
    client.deployment = deployment
    return client


def test_enabled_when_deployment_matches() -> None:
    with patch(
        "clients.client_factory.create_claude_client",
        return_value=_client(ClaudeDeployment.ENTERPRISE),
    ):
        assert (
            is_deployment_enabled(ClaudeDeployment.ENTERPRISE, "claude-ai-user-usage")
            is True
        )


def test_skipped_when_platform_kind_runs_in_enterprise_mode() -> None:
    with patch(
        "clients.client_factory.create_claude_client",
        return_value=_client(ClaudeDeployment.ENTERPRISE),
    ):
        assert (
            is_deployment_enabled(
                ClaudeDeployment.PLATFORM, "claude-platform-usage-record"
            )
            is False
        )


def test_skipped_when_enterprise_kind_runs_in_platform_mode() -> None:
    with patch(
        "clients.client_factory.create_claude_client",
        return_value=_client(ClaudeDeployment.PLATFORM),
    ):
        assert (
            is_deployment_enabled(ClaudeDeployment.ENTERPRISE, "claude-ai-user-cost")
            is False
        )
