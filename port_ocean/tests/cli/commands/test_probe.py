"""Unit tests for the probe CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from port_ocean.cli.commands.probe import _parse_kinds, probe
from port_ocean.core.probe import ProbeMode, ProbeReportingMode


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("repository", ["repository"]),
        ("repository,pull-request", ["repository", "pull-request"]),
        ("repository pull-request", ["repository", "pull-request"]),
        ("repository, pull-request", ["repository", "pull-request"]),
    ],
)
def test_parse_kinds_splits_comma_and_space_separated_values(
    value: str | None,
    expected: list[str] | None,
) -> None:
    # Act
    result = _parse_kinds(click.Context(click.Command("probe")), MagicMock(), value)

    # Assert
    assert result == expected


def test_parse_kinds_raises_for_empty_value() -> None:
    # Act / Assert
    with pytest.raises(click.BadParameter, match="must contain at least one kind"):
        _parse_kinds(click.Context(click.Command("probe")), MagicMock(), " , ")


@patch("port_ocean.cli.commands.probe.run_probe")
def test_probe_command_invokes_run_probe_with_parsed_kinds(
    mock_run_probe: MagicMock,
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()

    # Act
    result = runner.invoke(
        probe,
        [
            str(tmp_path),
            "--probe-id",
            "probe-123",
            "--kinds",
            "repository,pull-request",
            "--mode",
            "shallow",
            "--reporting-mode",
            "file",
        ],
    )

    # Assert
    assert result.exit_code == 0
    assert "Probe succeeded" in result.output
    mock_run_probe.assert_called_once_with(
        "probe-123",
        str(tmp_path),
        "INFO",
        kinds=["repository", "pull-request"],
        mode=ProbeMode.SHALLOW,
        reporting_mode=ProbeReportingMode.FILE,
    )


@patch("port_ocean.cli.commands.probe.run_probe")
def test_probe_command_defaults_to_log_reporting(
    mock_run_probe: MagicMock,
    tmp_path: Path,
) -> None:
    runner = CliRunner()

    result = runner.invoke(probe, [str(tmp_path)])

    assert result.exit_code == 0
    assert mock_run_probe.call_args.kwargs["reporting_mode"] is ProbeReportingMode.LOG


@patch(
    "port_ocean.cli.commands.probe.run_probe",
    side_effect=RuntimeError("connection failed"),
)
def test_probe_command_wraps_failures_in_click_exception(
    mock_run_probe: MagicMock,
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()

    # Act
    result = runner.invoke(probe, [str(tmp_path)])

    # Assert
    assert result.exit_code != 0
    assert "Probe failed: connection failed" in result.output
    mock_run_probe.assert_called_once()
