from typing import Any

from github.core.exporters.pull_request_review_stats import compute_review_stats


def _review(
    review_id: int,
    *,
    login: str,
    state: str,
    body: str,
    submitted_at: str,
    user_type: str = "User",
) -> dict[str, Any]:
    return {
        "id": review_id,
        "body": body,
        "state": state,
        "submitted_at": submitted_at,
        "user": {"login": login, "type": user_type},
        "__commentType": "review-summary",
    }


def test_review_stats_separate_humans_bots_and_empty_approvals() -> None:
    comments = [
        {
            "id": 1,
            "body": "please split this",
            "created_at": "2026-10-01T01:00:00Z",
            "user": {"login": "reviewer", "type": "User"},
            "__commentType": "comment",
        },
        {
            "id": 2,
            "body": "ci failed",
            "created_at": "2026-10-01T01:30:00Z",
            "user": {"login": "github-actions[bot]", "type": "Bot"},
            "__commentType": "comment",
        },
        {
            "id": 3,
            "body": "nit",
            "created_at": "2026-10-01T00:30:00Z",
            "user": {"login": "my-ci", "type": "User"},
            "__commentType": "review",
        },
        _review(
            4,
            login="reviewer",
            state="APPROVED",
            body="",
            submitted_at="2026-10-01T03:00:00Z",
        ),
        _review(
            5,
            login="dependabot[bot]",
            state="APPROVED",
            body="lgtm from the bot",
            submitted_at="2026-10-01T02:00:00Z",
            user_type="Bot",
        ),
    ]
    pull_request = {
        "created_at": "2026-10-01T00:00:00Z",
        "draft": False,
    }
    timeline = [
        {"event": "ready_for_review", "created_at": "2026-10-01T00:00:00Z"},
    ]

    stats = compute_review_stats(comments, pull_request, timeline)

    assert stats["humanApprovals"] == 1
    assert stats["humanComments"] == 2
    assert stats["botComments"] == 2
    assert stats["firstHumanReview"] == "2026-10-01T00:30:00Z"
    assert stats["firstApproval"] == "2026-10-01T03:00:00Z"
    assert stats["waitOnHumanHours"] == 0.5


def test_wait_uses_review_requested_when_the_pull_request_was_never_draft() -> None:
    comments = [
        _review(
            1,
            login="reviewer",
            state="COMMENTED",
            body="looks fine",
            submitted_at="2026-10-02T00:00:00Z",
        )
    ]
    stats = compute_review_stats(
        comments,
        {"created_at": "2026-10-01T00:00:00Z", "draft": False},
        [{"event": "review_requested", "created_at": "2026-10-01T12:00:00Z"}],
    )
    assert stats["firstHumanReview"] == "2026-10-02T00:00:00Z"
    assert stats["firstApproval"] is None
    assert stats["waitOnHumanHours"] == 12.0
    assert stats["humanComments"] == 1


def test_draft_without_ready_event_has_no_wait() -> None:
    stats = compute_review_stats(
        [],
        {"created_at": "2026-10-01T00:00:00Z", "draft": True},
        [],
    )
    assert stats["waitOnHumanHours"] is None
    assert stats["firstHumanReview"] is None
    assert stats["humanApprovals"] == 0
