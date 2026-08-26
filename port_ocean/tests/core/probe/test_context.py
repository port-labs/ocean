from datetime import datetime, timezone
from pathlib import Path

from port_ocean.core.probe import ProbeCheck, ProbeConfig, ProbeContext, ProbeStatus


def test_local_probe_context_has_no_probe_id() -> None:
    context = ProbeContext()

    assert context.probe_id is None
    assert context.available_kinds == []
    assert context.checks == []
    assert context.ended_at is None
    context.update_progress()
    context.finalize()
    assert context.ended_at is not None
    context.fail()


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
