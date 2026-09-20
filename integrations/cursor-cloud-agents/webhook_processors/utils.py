from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from exporter_factory import create_runs_exporter


def _parse_iso8601(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_webhook_timestamp(payload: dict[str, Any]) -> datetime:
    raw_timestamp = payload.get("timestamp")
    parsed = _parse_iso8601(raw_timestamp)
    if parsed is not None:
        return parsed
    if isinstance(raw_timestamp, str) and raw_timestamp:
        logger.warning(f"Invalid Cursor webhook timestamp {raw_timestamp!r}, using now")
    return datetime.now(timezone.utc)


def _pick_newest_run_id_at_or_before(
    runs: list[dict[str, Any]], webhook_time: datetime
) -> str | None:
    for run in runs:
        run_id = run.get("id")
        created_at = _parse_iso8601(run.get("createdAt"))
        if not run_id or created_at is None:
            continue
        if created_at <= webhook_time:
            return str(run_id)
    return None


async def resolve_newest_run_id_at_or_before(
    agent_id: str, webhook_time: datetime
) -> str | None:
    runs_exporter = create_runs_exporter()
    try:
        runs = await runs_exporter.list_first_page(agent_id)
    except Exception as error:
        logger.warning(
            f"Failed to list Cursor runs for agent {agent_id} "
            f"while resolving webhook run id: {error}"
        )
        return None
    return _pick_newest_run_id_at_or_before(runs, webhook_time)
