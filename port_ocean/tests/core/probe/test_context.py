from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from port_ocean.core.probe import (
    ProbeCheck,
    ProbeConfig,
    ProbeContext,
    ProbeMode,
    ProbeStatus,
)


def test_local_probe_context_has_no_probe_id() -> None:
    context = ProbeContext()

    assert context.probe_id is None
    assert context.available_kinds == []
    assert context.checks == []
    assert context.ended_at is None
    assert context.build_request_body() == {
        "started_at": context.started_at.isoformat(),
        "ended_at": None,
        "checks": [],
    }
    context.update_progress()
    context.finalize()
    assert context.ended_at is not None
    context.fail()


def test_local_probe_logs_the_request_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "port_ocean.core.probe.context.logger.info",
        lambda message, **kwargs: recorded.append((message, kwargs)),
    )
    context = ProbeContext()
    context.checks.append(ProbeCheck(kind="repository"))
    context.update_progress()

    assert recorded == [
        (
            "Local probe: skipping progress update",
            {"request_body": context.build_request_body()},
        )
    ]


def test_reported_probe_context_keeps_the_given_probe_id() -> None:
    context = ProbeContext("abc-123")

    assert context.probe_id == "abc-123"
    context.update_progress()
    context.finalize()
    context.fail()


def test_context_records_started_at_and_can_store_checks() -> None:
    before = datetime.now(timezone.utc)
    context = ProbeContext()
    after = datetime.now(timezone.utc)

    assert before <= context.started_at <= after
    context.checks.append(
        ProbeCheck(
            status=ProbeStatus.SUCCESS,
            message="auth succeeded",
            kind="repository",
            scopes={"org": "port-team"},
        )
    )
    context.finalize()

    assert context.checks[0].status is ProbeStatus.SUCCESS
    assert context.checks[0].kind == "repository"
    assert context.checks[0].scopes == {"org": "port-team"}
    assert context.ended_at is not None
    assert context.ended_at >= context.started_at


def test_build_request_body_serializes_timestamps_and_checks() -> None:
    context = ProbeContext()
    context.checks.append(
        ProbeCheck(
            status=ProbeStatus.SUCCESS,
            message="auth succeeded",
            kind="repository",
            scopes={"org": "port-team"},
        )
    )
    context.finalize()

    body = context.build_request_body()

    assert body["started_at"] == context.started_at.isoformat()
    assert body["ended_at"] == context.ended_at.isoformat()
    assert body["checks"] == [
        {
            "status": ProbeStatus.SUCCESS,
            "message": "auth succeeded",
            "kind": "repository",
            "scopes": {"org": "port-team"},
        }
    ]


def test_add_scopes_publishes_pending_checks_for_every_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress = MagicMock()
    context = ProbeContext()
    context.available_kinds = ["repository", "issue"]
    monkeypatch.setattr(context, "update_progress", progress)

    port_labs = {"org": "port-labs"}
    pending = context.add_scopes(port_labs, {"org": "port-team"})
    port_labs["org"] = "mutated"

    assert [(check.kind, check.status, check.scopes) for check in context.checks] == [
        ("repository", ProbeStatus.PENDING, {"org": "port-labs"}),
        ("issue", ProbeStatus.PENDING, {"org": "port-labs"}),
        ("repository", ProbeStatus.PENDING, {"org": "port-team"}),
        ("issue", ProbeStatus.PENDING, {"org": "port-team"}),
    ]
    assert pending[0] == context.checks[:2]
    assert pending[1] == context.checks[2:]
    progress.assert_called_once()


def test_add_scopes_with_no_arguments_adds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress = MagicMock()
    context = ProbeContext()
    context.available_kinds = ["repository"]
    monkeypatch.setattr(context, "update_progress", progress)

    assert context.add_scopes() == []
    assert context.checks == []
    progress.assert_not_called()


def test_initialize_loads_kinds_from_the_integration_spec(
    tmp_path: Path,
) -> None:
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.yaml").write_text("""
features:
  - type: exporter
    resources:
      - kind: repository
      - kind: issue
""")

    context = ProbeContext("abc-123")
    context.initialize(ProbeConfig(path=tmp_path, kinds=["repository"]))

    assert context.available_kinds == ["repository", "issue"]
    assert context.config.kinds == ["repository"]
    assert context.config.mode is ProbeMode.SHALLOW
