from importlib import import_module
from unittest.mock import MagicMock

from click.testing import CliRunner
from pytest import MonkeyPatch

from port_ocean.cli.commands.main import cli_start
from port_ocean.core.probe import ProbeMode

probe_module = import_module("port_ocean.cli.commands.probe")


def test_probe_command_passes_probe_id_through(monkeypatch: MonkeyPatch) -> None:
    # Arrange
    run_probe = MagicMock()
    monkeypatch.setattr(probe_module, "run_probe", run_probe)

    # Act
    result = CliRunner().invoke(cli_start, ["probe", ".", "--probe-id", "abc-123"])

    # Assert
    assert result.exit_code == 0
    assert "Probe succeeded" in result.output
    run_probe.assert_called_once_with("abc-123", ".", "INFO", mode=ProbeMode.SHALLOW)


def test_probe_command_reads_probe_id_from_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    run_probe = MagicMock()
    monkeypatch.setattr(probe_module, "run_probe", run_probe)
    monkeypatch.setenv("OCEAN__PROBE_ID", "from-env")

    # Act
    result = CliRunner().invoke(cli_start, ["probe", "."])

    # Assert
    assert result.exit_code == 0
    run_probe.assert_called_once_with("from-env", ".", "INFO", mode=ProbeMode.SHALLOW)


def test_probe_command_runs_locally_without_a_probe_id(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    run_probe = MagicMock()
    monkeypatch.setattr(probe_module, "run_probe", run_probe)
    monkeypatch.delenv("OCEAN__PROBE_ID", raising=False)

    # Act
    result = CliRunner().invoke(cli_start, ["probe", "."])

    # Assert
    assert result.exit_code == 0
    run_probe.assert_called_once_with(None, ".", "INFO", mode=ProbeMode.SHALLOW)


def test_probe_command_returns_nonzero_when_probe_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    run_probe = MagicMock(side_effect=RuntimeError("bad credentials"))
    monkeypatch.setattr(probe_module, "run_probe", run_probe)

    # Act
    result = CliRunner().invoke(cli_start, ["probe", ".", "--probe-id", "abc-123"])

    # Assert
    assert result.exit_code == 1
    assert "Probe failed: bad credentials" in result.output


def test_probe_command_injects_mode(monkeypatch: MonkeyPatch) -> None:
    run_probe = MagicMock()
    monkeypatch.setattr(probe_module, "run_probe", run_probe)

    result = CliRunner().invoke(cli_start, ["probe", ".", "--mode", "shallow"])

    assert result.exit_code == 0
    run_probe.assert_called_once_with(None, ".", "INFO", mode=ProbeMode.SHALLOW)
