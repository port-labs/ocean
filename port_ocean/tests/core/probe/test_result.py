from datetime import datetime, timezone

from port_ocean.core.probe import ProbeCheck, ProbeResult, ProbeStatus


def test_probe_result_is_initialized_with_a_start_time_and_empty_results() -> None:
    before = datetime.now(timezone.utc)
    result = ProbeResult()
    after = datetime.now(timezone.utc)

    assert before <= result.probe_start <= after
    assert result.probe_end is None
    assert result.results == []


def test_probe_result_can_record_scoped_checks() -> None:
    result = ProbeResult()

    result.results.append(
        ProbeCheck(
            status=ProbeStatus.SUCCESS,
            message="auth succeeded",
            kind="repository",
            scopes={"org": "port-team"},
        )
    )
    result.probe_end = datetime.now(timezone.utc)

    assert result.results[0].status is ProbeStatus.SUCCESS
    assert result.results[0].kind == "repository"
    assert result.results[0].scopes == {"org": "port-team"}
    assert result.probe_end is not None
    assert result.probe_end >= result.probe_start


def test_probe_check_defaults_to_pending() -> None:
    check = ProbeCheck()

    assert check.status is ProbeStatus.PENDING
    assert check.message is None
    assert check.kind is None
    assert check.scopes == {}
