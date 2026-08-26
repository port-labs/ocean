from port_ocean.core.probe import ProbeCheck, ProbeMode, ProbeStatus


def test_probe_check_defaults_to_pending() -> None:
    check = ProbeCheck()

    assert check.status is ProbeStatus.PENDING
    assert check.message is None
    assert check.kind is None
    assert check.scopes == {}


def test_probe_mode_starts_with_shallow() -> None:
    assert ProbeMode.SHALLOW == "shallow"
    assert list(ProbeMode) == [ProbeMode.SHALLOW]
