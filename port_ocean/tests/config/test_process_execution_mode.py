import pytest

from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.core.models import ProcessExecutionMode


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OCEAN__INTEGRATION__TYPE", "test")
    monkeypatch.setenv("OCEAN__INTEGRATION__IDENTIFIER", "test-id")


def test_multi_process_execution_mode_is_deprecated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv(
        "OCEAN__PROCESS_EXECUTION_MODE", ProcessExecutionMode.multi_process
    )

    config = IntegrationConfiguration()

    assert config.process_execution_mode == ProcessExecutionMode.single_process


def test_single_process_execution_mode_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)

    config = IntegrationConfiguration()

    assert config.process_execution_mode == ProcessExecutionMode.single_process
