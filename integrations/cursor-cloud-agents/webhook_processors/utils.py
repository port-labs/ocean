from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from clients.client_factory import create_cursor_agents_client
from clients.cursor_agents_client import CursorAgentsClient
from clients.run_reads import list_first_runs_page


def extract_port_run_id_from_request(request: object) -> str | None:
    """Read the Port workflow node run id from the callback URL for HMAC verification.

    The v0 webhook URL is registered once at ``create_agent`` launch and is not
    used to correlate which Port run to complete.
    """
    path_params = getattr(request, "path_params", None)
    if not isinstance(path_params, dict):
        return None
    run_id = path_params.get("run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    return None


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


def _parse_run_created_at(raw_created_at: object) -> datetime | None:
    return _parse_iso8601(raw_created_at)


def resolve_cursor_run_id_from_runs(
    runs: list[dict[str, Any]], webhook_time: datetime
) -> str | None:
    """Pick the newest Cursor run that started on or before the webhook time.

    ``runs`` must be the first List Runs page (newest first).
    """
    for run in runs:
        run_id = run.get("id")
        created_at = _parse_run_created_at(run.get("createdAt"))
        if not run_id or created_at is None:
            continue
        if created_at <= webhook_time:
            return str(run_id)
    return None


async def resolve_cursor_run_id_for_webhook(
    agent_id: str,
    webhook_time: datetime,
    client: CursorAgentsClient | None = None,
) -> str | None:
    cursor_client = client or create_cursor_agents_client()
    try:
        runs = await list_first_runs_page(cursor_client, agent_id)
    except Exception as error:
        logger.warning(
            f"Failed to list Cursor runs for agent {agent_id} "
            f"while resolving webhook run id: {error}"
        )
        return None
    return resolve_cursor_run_id_from_runs(runs, webhook_time)


async def resolve_tracked_run(
    agent_id: str, cursor_run_id: str | None
) -> IntegrationRun | None:
    """Find the in-progress Port run for this agent-status webhook.

    ``trigger_agent`` sets ``externalRunId`` to the Cursor run id; ``create_agent``
    uses the Cursor agent id. Try the resolved Cursor run id first, then the
    agent id for the initial create.
    """
    if cursor_run_id:
        run = await ocean.port_client.find_run_by_external_id(cursor_run_id)
        if run and ocean.port_client.is_run_in_progress(run):
            return run

    run = await ocean.port_client.find_run_by_external_id(agent_id)
    if run and ocean.port_client.is_run_in_progress(run):
        return run

    return None
