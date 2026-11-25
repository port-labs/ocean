from typing import Any

from clients.parsing import (
    parse_session_message_best_effort,
    parse_session_response_best_effort,
    require_session_response,
)


def _session(**overrides: Any) -> dict[str, Any]:
    base = {
        "session_id": "devin-1",
        "url": "https://app.devin.ai/sessions/devin-1",
        "status": "running",
        "tags": ["port:pending:inst"],
        "created_at": 1,
        "updated_at": 2,
    }
    base.update(overrides)
    return base


def test_require_session_response_strips_invalid_pull_requests() -> None:
    session = require_session_response(
        _session(pull_requests=[{"pr_url": "https://pr/1"}, {"no_url": True}, None])
    )

    assert [pr.pr_url for pr in session.pull_requests] == ["https://pr/1"]


def test_parse_session_response_best_effort_fills_missing_url() -> None:
    payload = _session()
    del payload["url"]
    session = parse_session_response_best_effort(payload)

    assert session is not None
    assert session.url == ""


def test_parse_session_response_best_effort_skips_missing_session_id() -> None:
    payload = _session()
    del payload["session_id"]

    assert parse_session_response_best_effort(payload) is None


def test_parse_session_message_best_effort_skips_invalid() -> None:
    assert (
        parse_session_message_best_effort(
            {"event_id": "e1", "source": "devin", "message": "hi", "created_at": 1}
        )
        is not None
    )
    assert parse_session_message_best_effort({"event_id": "e2"}) is None
