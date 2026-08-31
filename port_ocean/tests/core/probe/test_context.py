"""Unit tests for probe context."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import (
    ProbeCheck,
    ProbeCheckStatus,
    ProbeReportingMode,
    ProbeStatus,
)
from port_ocean.core.probe.reporters.file import FileProbeReporter
from port_ocean.core.probe.reporters.log import LogProbeReporter
from port_ocean.exceptions.probe import InvalidProbeKindsError, ProbeNotInitializedError


def test_starts_with_empty_state() -> None:
    # Arrange
    started_before = datetime.now(timezone.utc)

    # Act
    context = ProbeContext()

    # Assert
    assert context.probe_id is None
    assert context.available_kinds == []
    assert context.config == ProbeConfig()
    assert context.started_at >= started_before
    assert context.ended_at is None
    assert context.status == ProbeStatus.IN_PROGRESS
    assert context.message is None
    assert context.reporter is None
    assert context.checks == []


@patch("port_ocean.core.probe.context.ProbeContext.update_progress", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_add_scopes_creates_check_per_kind_and_scope(
    mock_update_progress: AsyncMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository", "pull-request"]

    # Act
    new_checks = await context.add_scopes({"org": "acme"}, {"org": "other"})

    # Assert
    assert len(new_checks) == 4
    assert {(check.kind, check.scopes["org"]) for check in new_checks} == {
        ("repository", "acme"),
        ("repository", "other"),
        ("pull-request", "acme"),
        ("pull-request", "other"),
    }
    mock_update_progress.assert_awaited_once()


@patch("port_ocean.core.probe.context.ProbeContext.update_progress", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_add_scopes_copies_scope_dict(mock_update_progress: AsyncMock) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]
    scope: dict[str, str | int] = {"org": "acme"}

    # Act
    new_checks = await context.add_scopes(scope)
    scope["org"] = "mutated"

    # Assert
    assert new_checks[0].scopes == {"org": "acme"}


@patch("port_ocean.core.probe.context.ProbeContext.update_progress", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_add_scopes_returns_only_new_checks(mock_update_progress: AsyncMock) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]
    existing_check = ProbeCheck(kind="existing", scopes={"org": "old"})
    context.checks.append(existing_check)

    # Act
    new_checks = await context.add_scopes({"org": "new"})

    # Assert
    assert len(new_checks) == 1
    assert existing_check not in new_checks


def test_build_request_body() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    ended_at = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
    context.ended_at = ended_at
    context.status = ProbeStatus.COMPLETED
    context.message = "probe finished"
    context.checks = [
        ProbeCheck(
            kind="repository",
            scopes={"org": "acme"},
            status=ProbeCheckStatus.SUCCESS,
            message="ok",
        )
    ]

    # Act
    body = context.build_request_body()

    # Assert
    assert body == {
        "probeId": "probe-1",
        "status": "COMPLETED",
        "probeMode": "shallow",
        "startedAt": context.started_at.isoformat(),
        "endedAt": ended_at.isoformat(),
        "message": "probe finished",
        "checks": [
            {
                "status": "SUCCESS",
                "message": "ok",
                "kind": "repository",
                "scopes": {"org": "acme"},
            }
        ],
    }


def test_build_request_body_when_probe_in_progress() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")

    # Act
    body = context.build_request_body()

    # Assert
    assert body["probeId"] == "probe-1"
    assert body["status"] == "IN_PROGRESS"
    assert body["probeMode"] == "shallow"
    assert "endedAt" not in body
    assert "message" not in body
    assert body["checks"] == []


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=["repository"])
@pytest.mark.asyncio
async def test_initialize_sets_config_and_available_kinds(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    context.status = ProbeStatus.COMPLETED
    config = ProbeConfig(path=Path("/integration"), kinds=["repository"])

    # Act
    with patch.object(context, "update_progress", new_callable=AsyncMock) as mock_update_progress:
        await context.initialize(config)

    # Assert
    assert context.config is config
    assert context.available_kinds == ["repository"]
    assert context.status == ProbeStatus.IN_PROGRESS
    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))
    mock_update_progress.assert_awaited_once_with()


@patch(
    "port_ocean.core.probe.context.get_spec_kinds",
    return_value=["repository", "pull-request"],
)
@pytest.mark.asyncio
async def test_initialize_deduplicates_injected_kinds(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    config = ProbeConfig(
        path=Path("/integration"),
        kinds=["repository", "repository", "pull-request", "repository"],
    )

    # Act
    with patch.object(context, "update_progress", new_callable=AsyncMock):
        await context.initialize(config)

    # Assert
    assert context.available_kinds == ["pull-request", "repository"]
    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))


@patch(
    "port_ocean.core.probe.context.get_spec_kinds",
    return_value=["repository", "pull-request"],
)
@pytest.mark.asyncio
async def test_initialize_raises_for_invalid_kinds(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    config = ProbeConfig(
        path=Path("/integration"),
        kinds=["repository", "fake-kind"],
    )

    # Act / Assert
    with pytest.raises(
        InvalidProbeKindsError, match="Invalid probe kinds: \\['fake-kind'\\]"
    ):
        await context.initialize(config)

    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=[])
@pytest.mark.asyncio
async def test_initialize_uses_default_config_when_none(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    context.status = ProbeStatus.COMPLETED

    # Act
    with patch.object(context, "update_progress", new_callable=AsyncMock) as mock_update_progress:
        await context.initialize()

    # Assert
    assert context.config == ProbeConfig()
    assert context.status == ProbeStatus.IN_PROGRESS
    mock_get_spec_kinds.assert_called_once_with(Path("."))
    mock_update_progress.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("reporting_mode", "expected_reporter_type"),
    [
        (ProbeReportingMode.LOG, LogProbeReporter),
        (ProbeReportingMode.FILE, FileProbeReporter),
    ],
)
@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=[])
@pytest.mark.asyncio
async def test_initialize_creates_reporter_for_reporting_mode(
    mock_get_spec_kinds: MagicMock,
    reporting_mode: ProbeReportingMode,
    expected_reporter_type: type[LogProbeReporter] | type[FileProbeReporter],
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    config = ProbeConfig(reporting_mode=reporting_mode)

    # Act
    with patch.object(context, "update_progress", new_callable=AsyncMock):
        await context.initialize(config)

    # Assert
    assert isinstance(context.reporter, expected_reporter_type)
    assert context.reporter.config is config
    mock_get_spec_kinds.assert_called_once_with(Path("."))


@pytest.mark.asyncio
async def test_update_progress_raises_when_reporter_not_initialized() -> None:
    # Act / Assert
    with pytest.raises(ProbeNotInitializedError, match="Reporter is not initialized"):
        await ProbeContext().update_progress()


@pytest.mark.asyncio
async def test_update_progress_reports_merged_payload() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-123")
    context.reporter = AsyncMock()

    # Act
    await context.update_progress()

    # Assert
    context.reporter.report.assert_awaited_once_with(context.build_request_body())


@pytest.mark.asyncio
async def test_finalize() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    started_before = datetime.now(timezone.utc)

    # Act
    with patch.object(context, "update_progress", new_callable=AsyncMock) as mock_update_progress:
        await context.finalize()

    # Assert
    assert context.ended_at is not None
    assert context.ended_at >= started_before
    assert context.status == ProbeStatus.COMPLETED
    mock_update_progress.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_fail() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    started_before = datetime.now(timezone.utc)
    failure_message = "connection timed out"

    # Act
    with patch.object(context, "update_progress", new_callable=AsyncMock) as mock_update_progress:
        await context.fail(failure_message)

    # Assert
    assert context.ended_at is not None
    assert context.ended_at >= started_before
    assert context.status == ProbeStatus.FAILED
    assert context.message == failure_message
    mock_update_progress.assert_awaited_once_with()
