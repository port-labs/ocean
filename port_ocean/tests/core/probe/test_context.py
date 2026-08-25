from pathlib import Path

from port_ocean.core.probe import ProbeConfig, ProbeContext


def test_local_probe_context_has_no_probe_id() -> None:
    context = ProbeContext()

    assert context.probe_id is None
    assert context.available_kinds == []
    context.update_progress()
    context.finalize()
    assert context.result.probe_end is not None
    context.fail()


def test_reported_probe_context_keeps_the_given_probe_id() -> None:
    context = ProbeContext("abc-123")

    assert context.probe_id == "abc-123"
    context.update_progress()
    context.finalize()
    context.fail()


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
