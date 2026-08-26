from port_ocean.core.probe import ProbeCheck, ProbeStatus


def test_probe_check_defaults_to_pending() -> None:
    check = ProbeCheck()

    assert check.status is ProbeStatus.PENDING
    assert check.message is None
    assert check.kind is None
    assert check.scopes == {}
