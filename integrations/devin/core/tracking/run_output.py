from datetime import datetime, timezone
from typing import Any

from clients.models import SessionResponse


def iso_from_epoch(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def started_output(session: SessionResponse, sent_at: int) -> dict[str, Any]:
    return {
        "sessionId": session.session_id,
        "url": session.url,
        "startedAt": iso_from_epoch(sent_at),
    }


def completion_output(
    session: SessionResponse,
    sent_at: int,
    ended_at: int,
    last_devin_message: str | None,
) -> dict[str, Any]:
    return {
        **started_output(session, sent_at),
        "endedAt": iso_from_epoch(ended_at),
        "durationSeconds": max(ended_at - sent_at, 0),
        "status": session.status,
        "statusDetail": session.status_detail,
        "pullRequests": [pr.pr_url for pr in session.pull_requests],
        "structuredOutput": session.structured_output,
        "acusConsumed": session.acus_consumed,
        "onDemandUsage": session.on_demand_usage,
        "lastMessage": last_devin_message,
    }


def completion_summary(output: dict[str, Any]) -> str:
    """One-line run message; action runs don't persist `output`, so it carries the essentials."""
    parts = [
        f"Devin session {output['sessionId']} turn ended "
        f"after {output['durationSeconds']}s ({output['status']}"
        + (f"/{output['statusDetail']}" if output.get("statusDetail") else "")
        + ")"
    ]
    if output["pullRequests"]:
        parts.append("PRs: " + ", ".join(output["pullRequests"]))
    parts.append(f"ACUs: {output['acusConsumed']}")
    return ". ".join(parts)
