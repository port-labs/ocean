from importlib import import_module
from unittest.mock import MagicMock

from click.testing import CliRunner
from pytest import MonkeyPatch

from port_ocean.cli.commands.main import cli_start

probe_module = import_module("port_ocean.cli.commands.probe")


def test_probe_command_runs_registered_probe(monkeypatch: MonkeyPatch) -> None:
    # Arrange
    run_probe = MagicMock()
    monkeypatch.setattr(probe_module, "run_probe", run_probe)

    # Act
    result = CliRunner().invoke(cli_start, ["probe", "."])

    # Assert
    assert result.exit_code == 0
    assert "Probe succeeded" in result.output
    run_probe.assert_called_once_with(".", "INFO")


def test_probe_command_returns_nonzero_when_probe_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    run_probe = MagicMock(side_effect=RuntimeError("bad credentials"))
    monkeypatch.setattr(probe_module, "run_probe", run_probe)

    # Act
    result = CliRunner().invoke(cli_start, ["probe", "."])

    # Assert
    assert result.exit_code == 1
    assert "Probe failed: bad credentials" in result.output
