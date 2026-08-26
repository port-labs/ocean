from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pytest import MonkeyPatch

from port_ocean.core.probe import ProbeConfig, ProbeMode

run_module = import_module("port_ocean.run")


def test_run_probe_passes_given_probe_id_to_the_integration(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    integration = SimpleNamespace(run_probe=AsyncMock())
    app = SimpleNamespace(integration=integration)
    monkeypatch.setattr(run_module, "init_signal_handler", MagicMock())
    monkeypatch.setattr(run_module, "setup_logger", MagicMock())
    monkeypatch.setattr(run_module, "load_ocean_app", lambda path: app)

    # Act
    run_module.run_probe("abc-123", path=".", log_level="DEBUG")

    # Assert
    integration.run_probe.assert_awaited_once_with("abc-123", ProbeConfig(path="."))


def test_run_probe_passes_none_when_no_probe_id_is_given(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    integration = SimpleNamespace(run_probe=AsyncMock())
    app = SimpleNamespace(integration=integration)
    monkeypatch.setattr(run_module, "init_signal_handler", MagicMock())
    monkeypatch.setattr(run_module, "setup_logger", MagicMock())
    monkeypatch.setattr(run_module, "load_ocean_app", lambda path: app)

    # Act
    run_module.run_probe(path=".", log_level="DEBUG")

    # Assert
    integration.run_probe.assert_awaited_once_with(None, ProbeConfig(path="."))


def test_run_probe_passes_requested_kinds_in_config(
    monkeypatch: MonkeyPatch,
) -> None:
    # Arrange
    integration = SimpleNamespace(run_probe=AsyncMock())
    app = SimpleNamespace(integration=integration)
    monkeypatch.setattr(run_module, "init_signal_handler", MagicMock())
    monkeypatch.setattr(run_module, "setup_logger", MagicMock())
    monkeypatch.setattr(run_module, "load_ocean_app", lambda path: app)

    # Act
    run_module.run_probe(path=".", kinds=["repository", "issue"])

    # Assert
    integration.run_probe.assert_awaited_once_with(
        None, ProbeConfig(path=".", kinds=["repository", "issue"])
    )


def test_run_probe_injects_mode_in_config(
    monkeypatch: MonkeyPatch,
) -> None:
    integration = SimpleNamespace(run_probe=AsyncMock())
    app = SimpleNamespace(integration=integration)
    monkeypatch.setattr(run_module, "init_signal_handler", MagicMock())
    monkeypatch.setattr(run_module, "setup_logger", MagicMock())
    monkeypatch.setattr(run_module, "load_ocean_app", lambda path: app)

    run_module.run_probe(path=".", mode=ProbeMode.SHALLOW)

    integration.run_probe.assert_awaited_once_with(
        None, ProbeConfig(path=".", mode=ProbeMode.SHALLOW)
    )
