from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pytest import MonkeyPatch

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
    integration.run_probe.assert_awaited_once_with("abc-123")


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
    integration.run_probe.assert_awaited_once_with(None)
