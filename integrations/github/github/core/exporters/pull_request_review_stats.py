"""Per-pull-request review numbers stored on ``__reviewStats``.

- ``humanComments`` / ``botComments``: conversation comments, inline comments,
  and review bodies that contain text. A bot is a GitHub user of type ``Bot``.
- ``humanApprovals``: non-bot ``APPROVED`` reviews, including empty bodies.
- ``firstHumanReview``: earliest non-bot submitted review or inline comment.
  Pending reviews are skipped. Conversation comments do not move this.
- ``firstApproval``: earliest non-bot ``APPROVED`` review.
- ``waitOnHumanHours``: hours from the earliest ``ready_for_review``, otherwise
  the earliest ``review_requested``, otherwise ``created_at`` when the pull
  request is not a draft, until ``firstHumanReview``. Null when either side
  is missing.
"""

from datetime import datetime, timezone
from typing import Any

_Moment = tuple[datetime, str]


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_bot(comment: dict[str, Any]) -> bool:
    user = comment.get("user")
    return isinstance(user, dict) and user.get("type") == "Bot"


def _has_text(comment: dict[str, Any]) -> bool:
    body = comment.get("body")
    return isinstance(body, str) and bool(body.strip())


def _moment(comment: dict[str, Any]) -> _Moment | None:
    raw = comment.get("submitted_at") or comment.get("created_at")
    parsed = _parse_time(raw)
    if parsed is None or not isinstance(raw, str):
        return None
    return parsed, raw


def _earlier(current: _Moment | None, candidate: _Moment | None) -> _Moment | None:
    if candidate is None:
        return current
    if current is None or candidate[0] < current[0]:
        return candidate
    return current


def _earliest_event(timeline: list[dict[str, Any]], name: str) -> datetime | None:
    earliest: datetime | None = None
    for event in timeline:
        if event.get("event") != name:
            continue
        moment = _parse_time(event.get("created_at"))
        if moment is not None and (earliest is None or moment < earliest):
            earliest = moment
    return earliest


def _wait_start(
    pull_request: dict[str, Any], timeline: list[dict[str, Any]]
) -> datetime | None:
    ready = _earliest_event(timeline, "ready_for_review")
    if ready is not None:
        return ready
    requested = _earliest_event(timeline, "review_requested")
    if requested is not None:
        return requested
    if pull_request.get("draft") is True:
        return None
    return _parse_time(pull_request.get("created_at"))


def compute_review_stats(
    comments: list[dict[str, Any]],
    pull_request: dict[str, Any],
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    human_approvals = 0
    human_comments = 0
    bot_comments = 0
    first_human_review: _Moment | None = None
    first_approval: _Moment | None = None

    for comment in comments:
        kind = comment.get("__commentType")
        moment = _moment(comment)
        state = str(comment.get("state") or "").upper()
        bot = _is_bot(comment)

        if _has_text(comment):
            if bot:
                bot_comments += 1
            else:
                human_comments += 1

        if bot or moment is None:
            continue
        if kind == "review" or (kind == "review-summary" and state != "PENDING"):
            first_human_review = _earlier(first_human_review, moment)
        if kind == "review-summary" and state == "APPROVED":
            human_approvals += 1
            first_approval = _earlier(first_approval, moment)

    wait_hours = None
    start = _wait_start(pull_request, timeline)
    if start is not None and first_human_review is not None:
        elapsed_hours = (first_human_review[0] - start).total_seconds() / 3600
        wait_hours = round(max(elapsed_hours, 0.0), 2)

    return {
        "humanApprovals": human_approvals,
        "humanComments": human_comments,
        "botComments": bot_comments,
        "firstHumanReview": (
            None if first_human_review is None else first_human_review[1]
        ),
        "firstApproval": None if first_approval is None else first_approval[1],
        "waitOnHumanHours": wait_hours,
    }
