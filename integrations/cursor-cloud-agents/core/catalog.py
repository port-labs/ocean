from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from actions.utils import build_agent_link
from integration import ObjectKind

# v0 launch / webhook payloads carry run lifecycle statuses. Map them to v1 agent
# lifecycle values before upserting the cursor_agent blueprint.
_V0_TO_AGENT_STATUS = {
    "CREATING": "ACTIVE",
    "RUNNING": "ACTIVE",
    "STOPPED": "IDLE",
    "FINISHED": "IDLE",
    "ERROR": "IDLE",
    "CANCELLED": "IDLE",
    "EXPIRED": "ARCHIVED",
}


def format_datetime_for_catalog(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def enrich_v0_agent_raw_for_catalog(
    raw: dict[str, Any], *, console_host: str | None = None
) -> dict[str, Any]:
    """Map v0 agent / webhook snapshots onto the v1 fields used by port mappings."""
    if "repos" in raw or ("source" not in raw and "target" not in raw):
        return dict(raw)

    enriched = dict(raw)
    source = enriched.get("source")
    if isinstance(source, dict):
        repo_url = source.get("repository") or source.get("prUrl")
        if isinstance(repo_url, str) and repo_url:
            enriched["repos"] = [{"url": repo_url}]

    target = enriched.get("target")
    if isinstance(target, dict):
        target_url = target.get("url")
        if isinstance(target_url, str) and target_url:
            enriched["url"] = target_url

    agent_id = enriched.get("id")
    if not enriched.get("url") and console_host and isinstance(agent_id, str):
        enriched["url"] = build_agent_link(console_host, agent_id)

    return enriched


def normalize_agent_raw_for_catalog(
    raw: dict[str, Any], *, console_host: str | None = None
) -> dict[str, Any]:
    """Shape a Cursor agent API object for the `cursor_agent` blueprint.

    v0 launch and webhook snapshots use ``source``/``target`` instead of the
    v1 ``repos``/``url`` fields expected by port mappings. v0 run lifecycle
    ``status`` values are mapped to v1 agent lifecycle values.
    """
    normalized = enrich_v0_agent_raw_for_catalog(raw, console_host=console_host)
    status = normalized.get("status")
    if status in _V0_TO_AGENT_STATUS:
        normalized["status"] = _V0_TO_AGENT_STATUS[status]
    elif status is None:
        normalized.pop("status", None)

    # Optional url/date-time fields reject explicit null after jq mapping.
    if normalized.get("url") is None:
        normalized.pop("url", None)
    if normalized.get("updatedAt") is None:
        normalized.pop("updatedAt", None)
    return normalized


def normalize_run_raw_for_catalog(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    if normalized.get("updatedAt") is None:
        normalized.pop("updatedAt", None)
    return normalized


def normalize_raw_for_catalog(
    kind: str, raw: dict[str, Any], *, console_host: str | None = None
) -> dict[str, Any]:
    if kind == ObjectKind.AGENT:
        return normalize_agent_raw_for_catalog(raw, console_host=console_host)
    if kind == ObjectKind.RUN:
        return normalize_run_raw_for_catalog(raw)
    return raw
