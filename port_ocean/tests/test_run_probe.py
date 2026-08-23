from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pytest import MonkeyPatch

run_module = import_module("port_ocean.run")


def test_run_probe_loads_app_and_invokes_integration_probe(
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
    integration.run_probe.assert_awaited_once()
