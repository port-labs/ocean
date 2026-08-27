"""Unit tests for run_probe."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from port_ocean.core.probe import ProbeConfig, ProbeContext, ProbeMode
from port_ocean.run import run_probe


def _run_asyncio_run_immediately(coro: object) -> object:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)  # type: ignore[arg-type]
    finally:
        loop.close()


@patch("port_ocean.run.init_signal_handler")
@patch("port_ocean.run.setup_logger")
@patch("port_ocean.run.asyncio.run", side_effect=_run_asyncio_run_immediately)
@patch("port_ocean.run.load_ocean_app")
def test_run_probe_delegates_to_integration_with_probe_config(
    mock_load_ocean_app: MagicMock,
    mock_asyncio_run: MagicMock,
    mock_setup_logger: MagicMock,
    mock_init_signal_handler: MagicMock,
) -> None:
    # Arrange
    captured: dict[str, object] = {}
    mock_app = MagicMock()
    mock_load_ocean_app.return_value = mock_app

    async def capture_run_probe(
        probe_id: str | None,
        config: ProbeConfig | None = None,
    ) -> ProbeContext:
        captured["probe_id"] = probe_id
        captured["config"] = config
        return ProbeContext(probe_id)

    mock_app.integration.run_probe = capture_run_probe

    # Act
    run_probe(
        probe_id="probe-123",
        path="/integration",
        log_level="DEBUG",
        kinds=["repository"],
        mode=ProbeMode.SHALLOW,
    )

    # Assert
    mock_init_signal_handler.assert_called_once()
    mock_setup_logger.assert_called_once_with("DEBUG", enable_http_handler=True)
    mock_load_ocean_app.assert_called_once_with("/integration")
    mock_asyncio_run.assert_called_once()
    assert captured["probe_id"] == "probe-123"
    assert captured["config"] == ProbeConfig(
        path=Path("/integration"),
        kinds=["repository"],
        mode=ProbeMode.SHALLOW,
    )
