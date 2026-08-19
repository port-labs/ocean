from unittest.mock import patch

import pytest

from port_ocean.config.settings import IntegrationConfiguration


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OCEAN__INTEGRATION__TYPE", "test")
    monkeypatch.setenv("OCEAN__INTEGRATION__IDENTIFIER", "test-id")


def test_warns_when_process_execution_mode_env_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("OCEAN__PROCESS_EXECUTION_MODE", "multi_process")

    with patch("port_ocean.config.settings.logger") as mock_logger:
        IntegrationConfiguration()

    mock_logger.warning.assert_called_once()
    message = mock_logger.warning.call_args[0][0]
    assert "OCEAN__PROCESS_EXECUTION_MODE is no longer supported" in message
    assert mock_logger.warning.call_args[1]["process_execution_mode"] == "multi_process"


def test_no_warning_when_process_execution_mode_env_is_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("OCEAN__PROCESS_EXECUTION_MODE", raising=False)

    with patch("port_ocean.config.settings.logger") as mock_logger:
        IntegrationConfiguration()

    mock_logger.warning.assert_not_called()
