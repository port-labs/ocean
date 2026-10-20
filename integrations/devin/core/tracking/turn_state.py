"""Maps a Devin session's `status`/`status_detail` to the outcome of a Port run.

Everything here is an assumption about Devin's status transitions, kept in one
place so the spike against a real org only has to change this file and its
test matrix.
"""

from dataclasses import dataclass
from enum import StrEnum

# Devin may report epoch milliseconds; anything above this is not plausibly seconds.
_EPOCH_MILLISECONDS_THRESHOLD = 10**12

LIMIT_STATUS_DETAILS = frozenset(
    {
        "usage_limit_exceeded",
        "out_of_credits",
        "out_of_quota",
        "no_quota_allocation",
        "payment_declined",
        "org_usage_limit_exceeded",
        "user_usage_limit_exceeded",
        "total_session_limit_exceeded",
        "contract_expired",
    }
)


class TurnOutcome(StrEnum):
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class TurnState:
    outcome: TurnOutcome
    # Shown on the Port run; keep it to two words at most.
    label: str
    # A previous turn leaves the session in this same state, so it only counts
    # as this turn's end once Devin has replied since the turn started.
    requires_reply: bool = False


def classify(status: str, status_detail: str | None) -> TurnState:
    if status in ("new", "claimed"):
        return TurnState(TurnOutcome.IN_PROGRESS, "Starting")
    if status == "resuming":
        return TurnState(TurnOutcome.IN_PROGRESS, "Resuming")
    if status == "running":
        return _classify_running(status_detail)
    if status == "exit":
        return TurnState(TurnOutcome.SUCCEEDED, "Session ended")
    if status == "error":
        return TurnState(TurnOutcome.FAILED, "Session failed")
    if status == "suspended":
        return _classify_suspended(status_detail)
    return TurnState(TurnOutcome.IN_PROGRESS, "Unknown status")


def _classify_running(status_detail: str | None) -> TurnState:
    if status_detail == "waiting_for_user":
        return TurnState(TurnOutcome.SUCCEEDED, "Awaiting input", requires_reply=True)
    if status_detail == "finished":
        return TurnState(TurnOutcome.SUCCEEDED, "Finished", requires_reply=True)
    if status_detail == "waiting_for_approval":
        return TurnState(TurnOutcome.IN_PROGRESS, "Awaiting approval")
    return TurnState(TurnOutcome.IN_PROGRESS, "Devin working")


def _classify_suspended(status_detail: str | None) -> TurnState:
    if status_detail == "inactivity":
        return TurnState(TurnOutcome.SUCCEEDED, "Session idle", requires_reply=True)
    if status_detail == "user_request":
        return TurnState(TurnOutcome.FAILED, "User stopped")
    if status_detail in LIMIT_STATUS_DETAILS:
        return TurnState(TurnOutcome.FAILED, "Usage limit")
    if status_detail == "error":
        return TurnState(TurnOutcome.FAILED, "Session failed")
    return TurnState(TurnOutcome.FAILED, "Suspended")


def turn_has_ended(
    state: TurnState, updated_at: int, sent_at: int, devin_replied: bool
) -> bool:
    """Whether `state` belongs to the turn that started at `sent_at`.

    Sending a message bumps `updated_at` itself, so it cannot tell a fresh
    "waiting for user" from the previous turn's; those states require a Devin
    message since `sent_at` instead.
    """
    if state.outcome is TurnOutcome.IN_PROGRESS:
        return False
    if state.requires_reply:
        return devin_replied
    return to_epoch_seconds(updated_at) > sent_at


def to_epoch_seconds(value: int) -> int:
    if value > _EPOCH_MILLISECONDS_THRESHOLD:
        return value // 1000
    return value
