from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

from click.testing import CliRunner
from pytest import MonkeyPatch

from port_ocean.cli.commands.main import cli_start

probe_module = import_module("port_ocean.cli.commands.probe")


def test_probe_command_runs_registered_probe(monkeypatch: MonkeyPatch) -> None:
    run_probe = AsyncMock()
    app = SimpleNamespace(integration=SimpleNamespace(run_probe=run_probe))
    monkeypatch.setattr(probe_module, "load_ocean_app", lambda _path: app)
    monkeypatch.setattr(probe_module, "setup_logger", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(probe_module, "init_signal_handler", lambda: None)

    result = CliRunner().invoke(cli_start, ["probe", "."])

    assert result.exit_code == 0
    assert "Probe succeeded" in result.output
    run_probe.assert_awaited_once()


def test_probe_command_returns_nonzero_when_probe_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    run_probe = AsyncMock(side_effect=RuntimeError("bad credentials"))
    app = SimpleNamespace(integration=SimpleNamespace(run_probe=run_probe))
    monkeypatch.setattr(probe_module, "load_ocean_app", lambda _path: app)
    monkeypatch.setattr(probe_module, "setup_logger", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(probe_module, "init_signal_handler", lambda: None)

    result = CliRunner().invoke(cli_start, ["probe", "."])

    assert result.exit_code == 1
    assert "Probe failed: bad credentials" in result.output
