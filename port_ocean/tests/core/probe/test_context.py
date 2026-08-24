from port_ocean.core.probe import ProbeContext


def test_local_probe_context_has_no_probe_id() -> None:
    context = ProbeContext()

    assert context.probe_id is None
    context.update_progress()
    context.finalize()
    context.fail()


def test_reported_probe_context_keeps_the_given_probe_id() -> None:
    context = ProbeContext("abc-123")

    assert context.probe_id == "abc-123"
    context.update_progress()
    context.finalize()
    context.fail()
