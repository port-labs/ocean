import pytest

from core.tracking.turn_state import (
    LIMIT_STATUS_DETAILS,
    TurnOutcome,
    TurnState,
    classify,
    to_epoch_seconds,
    turn_has_ended,
)

IN_PROGRESS = TurnOutcome.IN_PROGRESS
SUCCEEDED = TurnOutcome.SUCCEEDED
FAILED = TurnOutcome.FAILED

ALL_STATUS_DETAILS = [
    None,
    "working",
    "waiting_for_user",
    "waiting_for_approval",
    "finished",
    "inactivity",
    "user_request",
    "error",
    *sorted(LIMIT_STATUS_DETAILS),
]


def _expected(status: str, detail: str | None) -> tuple[TurnOutcome, bool]:
    """The documented mapping, written out independently of the implementation."""
    if status in ("new", "claimed", "resuming"):
        return IN_PROGRESS, False
    if status == "running":
        if detail in ("waiting_for_user", "finished"):
            return SUCCEEDED, True
        return IN_PROGRESS, False
    if status == "exit":
        return SUCCEEDED, False
    if status == "error":
        return FAILED, False
    if status == "suspended":
        if detail == "inactivity":
            return SUCCEEDED, True
        return FAILED, False
    return IN_PROGRESS, False


@pytest.mark.parametrize(
    "status",
    ["new", "claimed", "running", "exit", "error", "suspended", "resuming", "???"],
)
@pytest.mark.parametrize("detail", ALL_STATUS_DETAILS)
def test_classify_matrix(status: str, detail: str | None) -> None:
    state = classify(status, detail)
    assert (state.outcome, state.requires_reply) == _expected(status, detail)
    assert len(state.label.split()) <= 2


@pytest.mark.parametrize(
    ("detail", "label"),
    [
        ("working", "Devin working"),
        ("waiting_for_approval", "Awaiting approval"),
        ("waiting_for_user", "Awaiting input"),
        ("finished", "Finished"),
    ],
)
def test_running_labels(detail: str, label: str) -> None:
    assert classify("running", detail).label == label


@pytest.mark.parametrize("detail", sorted(LIMIT_STATUS_DETAILS))
def test_limit_suspensions_fail_with_usage_limit_label(detail: str) -> None:
    assert classify("suspended", detail) == TurnState(FAILED, "Usage limit")


def test_in_progress_never_ends() -> None:
    assert not turn_has_ended(classify("running", "working"), 10_000, 1, True)


def test_reply_required_states_wait_for_devin_message() -> None:
    state = classify("running", "waiting_for_user")
    assert not turn_has_ended(state, updated_at=500, sent_at=100, devin_replied=False)
    assert turn_has_ended(state, updated_at=500, sent_at=100, devin_replied=True)


def test_other_ended_states_use_updated_at() -> None:
    state = classify("error", None)
    assert not turn_has_ended(state, updated_at=100, sent_at=100, devin_replied=False)
    assert turn_has_ended(state, updated_at=101, sent_at=100, devin_replied=False)


def test_updated_at_in_milliseconds_is_compared_in_seconds() -> None:
    state = classify("exit", None)
    sent_at = 1_760_000_000
    assert not turn_has_ended(state, sent_at * 1000, sent_at, False)
    assert turn_has_ended(state, (sent_at + 1) * 1000, sent_at, False)


def test_to_epoch_seconds() -> None:
    assert to_epoch_seconds(1_760_000_000) == 1_760_000_000
    assert to_epoch_seconds(1_760_000_000_123) == 1_760_000_000
