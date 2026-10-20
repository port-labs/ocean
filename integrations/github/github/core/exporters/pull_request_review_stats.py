from datetime import datetime, timezone
from typing import Any


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_bot_user(user: Any) -> bool:
    """GitHub accounts whose user type is Bot."""
    return isinstance(user, dict) and user.get("type") == "Bot"


def _event_times(timeline: list[dict[str, Any]], event_name: str) -> list[datetime]:
    times: list[datetime] = []
    for event in timeline:
        if event.get("event") != event_name:
            continue
        parsed = _parse_timestamp(event.get("created_at"))
        if parsed is not None:
            times.append(parsed)
    return times


def _wait_start(
    pull_request: dict[str, Any], timeline: list[dict[str, Any]]
) -> datetime | None:
    ready = _event_times(timeline, "ready_for_review")
    if ready:
        return min(ready)
    requested = _event_times(timeline, "review_requested")
    if requested:
        return min(requested)
    if pull_request.get("draft") is True:
        return None
    return _parse_timestamp(pull_request.get("created_at"))


def _has_text(comment: dict[str, Any]) -> bool:
    body = comment.get("body")
    return isinstance(body, str) and bool(body.strip())


def compute_review_stats(
    comments: list[dict[str, Any]],
    pull_request: dict[str, Any],
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-pull-request review numbers. Comments stay on the raw objects.

    Empty-body approvals still count. A review summary with text counts as a
    comment as well as an approval when its state is APPROVED.
    """
    human_approvals = 0
    human_comments = 0
    bot_comments = 0
    first_human_review: tuple[datetime, str] | None = None
    first_approval: tuple[datetime, str] | None = None

    for comment in comments:
        bot = is_bot_user(comment.get("user"))
        comment_type = comment.get("__commentType")
        timestamp = _parse_timestamp(
            comment.get("submitted_at") or comment.get("created_at")
        )
        raw_timestamp = comment.get("submitted_at") or comment.get("created_at")
        state = str(comment.get("state") or "").upper()

        if _has_text(comment) and comment_type in {
            "comment",
            "review",
            "review-summary",
        }:
            if bot:
                bot_comments += 1
            else:
                human_comments += 1

        if comment_type != "review-summary" or bot or timestamp is None:
            continue
        if not isinstance(raw_timestamp, str):
            continue
        if state == "PENDING":
            continue
        if first_human_review is None or timestamp < first_human_review[0]:
            first_human_review = (timestamp, raw_timestamp)
        if state == "APPROVED":
            human_approvals += 1
            if first_approval is None or timestamp < first_approval[0]:
                first_approval = (timestamp, raw_timestamp)

    # Inline review comments are review activity even without a submitted summary.
    for comment in comments:
        if comment.get("__commentType") != "review":
            continue
        if is_bot_user(comment.get("user")):
            continue
        timestamp = _parse_timestamp(comment.get("created_at"))
        raw_timestamp = comment.get("created_at")
        if timestamp is None or not isinstance(raw_timestamp, str):
            continue
        if first_human_review is None or timestamp < first_human_review[0]:
            first_human_review = (timestamp, raw_timestamp)

    wait_hours = None
    start = _wait_start(pull_request, timeline)
    if start is not None and first_human_review is not None:
        elapsed = (first_human_review[0] - start).total_seconds() / 3600
        wait_hours = round(max(elapsed, 0.0), 2)

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
