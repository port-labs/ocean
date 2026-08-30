"""Unit tests for probe context."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import (
    ProbeCheck,
    ProbeCheckStatus,
    ProbeReportStage,
    ProbeStatus,
)
from port_ocean.exceptions.probe import InvalidProbeKindsError


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
    assert context.checks == []


@patch("port_ocean.core.probe.context.ProbeContext.update_progress")
def test_add_scopes_creates_check_per_kind_and_scope(
    mock_update_progress: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository", "pull-request"]

    # Act
    new_checks = context.add_scopes({"org": "acme"}, {"org": "other"})

    # Assert
    assert len(new_checks) == 4
    assert {(check.kind, check.scopes["org"]) for check in new_checks} == {
        ("repository", "acme"),
        ("repository", "other"),
        ("pull-request", "acme"),
        ("pull-request", "other"),
    }
    mock_update_progress.assert_called_once()


@patch("port_ocean.core.probe.context.ProbeContext.update_progress")
def test_add_scopes_copies_scope_dict(mock_update_progress: MagicMock) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]
    scope = {"org": "acme"}

    # Act
    new_checks = context.add_scopes(scope)
    scope["org"] = "mutated"

    # Assert
    assert new_checks[0].scopes == {"org": "acme"}


@patch("port_ocean.core.probe.context.ProbeContext.update_progress")
def test_add_scopes_returns_only_new_checks(mock_update_progress: MagicMock) -> None:
    # Arrange
    context = ProbeContext()
    context.available_kinds = ["repository"]
    existing_check = ProbeCheck(kind="existing", scopes={"org": "old"})
    context.checks.append(existing_check)

    # Act
    new_checks = context.add_scopes({"org": "new"})

    # Assert
    assert len(new_checks) == 1
    assert existing_check not in new_checks


def test_build_request_body() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    ended_at = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
    context.ended_at = ended_at
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
    assert body["started_at"] == context.started_at.isoformat()
    assert body["ended_at"] == ended_at.isoformat()
    assert body["message"] is None
    assert body["checks"] == [
        {
            "status": ProbeCheckStatus.SUCCESS,
            "message": "ok",
            "kind": "repository",
            "scopes": {"org": "acme"},
        }
    ]


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=["repository"])
def test_initialize_sets_config_and_available_kinds(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    context.status = ProbeStatus.COMPLETED
    config = ProbeConfig(path=Path("/integration"), kinds=["repository"])

    # Act
    with patch.object(context, "update_progress") as mock_update_progress:
        context.initialize(config)

    # Assert
    assert context.config is config
    assert context.available_kinds == ["repository"]
    assert context.status == ProbeStatus.IN_PROGRESS
    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))
    mock_update_progress.assert_called_once_with(ProbeReportStage.INIT)


@patch(
    "port_ocean.core.probe.context.get_spec_kinds",
    return_value=["repository", "pull-request"],
)
def test_initialize_deduplicates_injected_kinds(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    config = ProbeConfig(
        path=Path("/integration"),
        kinds=["repository", "repository", "pull-request", "repository"],
    )

    # Act
    with patch.object(context, "update_progress"):
        context.initialize(config)

    # Assert
    assert set(context.available_kinds) == {"repository", "pull-request"}
    assert len(context.available_kinds) == 2
    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))


@patch(
    "port_ocean.core.probe.context.get_spec_kinds",
    return_value=["repository", "pull-request"],
)
def test_initialize_raises_for_invalid_kinds(
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
        context.initialize(config)

    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=[])
def test_initialize_uses_default_config_when_none(
    mock_get_spec_kinds: MagicMock,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    context.status = ProbeStatus.COMPLETED

    # Act
    with patch.object(context, "update_progress") as mock_update_progress:
        context.initialize()

    # Assert
    assert context.config == ProbeConfig()
    assert context.status == ProbeStatus.IN_PROGRESS
    mock_get_spec_kinds.assert_called_once_with(Path("."))
    mock_update_progress.assert_called_once_with(ProbeReportStage.INIT)


@pytest.mark.parametrize(
    ("stage", "expected_message"),
    [
        (
            ProbeReportStage.INIT,
            "Reporting probe start to Port for probe None",
        ),
        (
            ProbeReportStage.UPDATE,
            "Reporting probe progress to Port for probe None",
        ),
        (
            ProbeReportStage.FINALIZE,
            "Reporting final probe result to Port for probe None",
        ),
        (
            ProbeReportStage.FAIL,
            "Reporting fatal probe error to Port for probe None",
        ),
    ],
)
@patch("port_ocean.core.probe.context.logger")
def test_local_probe_logs_info_on_update_progress(
    mock_logger: MagicMock,
    stage: ProbeReportStage,
    expected_message: str,
) -> None:
    # Arrange
    context = ProbeContext()

    # Act
    context.update_progress(stage)

    # Assert
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args.args[0] == expected_message
    mock_logger.debug.assert_not_called()


@pytest.mark.parametrize(
    ("stage", "expected_message"),
    [
        (
            ProbeReportStage.INIT,
            "Reporting probe start to Port for probe probe-123",
        ),
        (
            ProbeReportStage.UPDATE,
            "Reporting probe progress to Port for probe probe-123",
        ),
        (
            ProbeReportStage.FINALIZE,
            "Reporting final probe result to Port for probe probe-123",
        ),
        (
            ProbeReportStage.FAIL,
            "Reporting fatal probe error to Port for probe probe-123",
        ),
    ],
)
@patch("port_ocean.core.probe.context.logger")
def test_remote_probe_logs_debug_on_update_progress(
    mock_logger: MagicMock,
    stage: ProbeReportStage,
    expected_message: str,
) -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-123")

    # Act
    context.update_progress(stage)

    # Assert
    mock_logger.debug.assert_called_once_with(expected_message)
    mock_logger.info.assert_not_called()


def test_finalize() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    started_before = datetime.now(timezone.utc)

    # Act
    with patch.object(context, "update_progress") as mock_update_progress:
        context.finalize()

    # Assert
    assert context.ended_at is not None
    assert context.ended_at >= started_before
    assert context.status == ProbeStatus.COMPLETED
    mock_update_progress.assert_called_once_with(ProbeReportStage.FINALIZE)


def test_fail() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    started_before = datetime.now(timezone.utc)

    # Act
    with patch.object(context, "update_progress") as mock_update_progress:
        context.fail("Jira rejected the configured credentials with HTTP 401")

    # Assert
    assert context.ended_at is not None
    assert context.ended_at >= started_before
    assert context.status == ProbeStatus.FAILED
    assert context.message == "Jira rejected the configured credentials with HTTP 401"
    mock_update_progress.assert_called_once_with(ProbeReportStage.FAIL)


def test_fail_message_is_reported() -> None:
    # Arrange
    context = ProbeContext(probe_id="probe-1")
    context.checks = [ProbeCheck(kind="project")]

    # Act
    context.fail("boom")

    # Assert
    body = context.build_request_body()
    assert body["message"] == "boom"
    # A failed probe reports the reason once, not once per unfinished check.
    assert body["checks"] == [
        {
            "status": ProbeCheckStatus.PENDING,
            "message": None,
            "kind": "project",
            "scopes": {},
        }
    ]
