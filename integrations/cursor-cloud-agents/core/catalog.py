from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean

from actions.utils import build_agent_link
from clients.cursor_agents_client import CursorAgentsClient
from clients.endpoints import v1_agent_run, v1_agent_usage
from integration import ObjectKind

_V1_AGENT_STATUSES = frozenset({"ACTIVE", "ARCHIVED"})


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

    v1 List/Get Agents use durable ``ACTIVE`` / ``ARCHIVED`` statuses. v0 launch
    and webhook snapshots reuse run lifecycle values (``CREATING``, ``RUNNING``,
    ``FINISHED``, …) which fail blueprint validation if passed through unchanged.
    """
    normalized = enrich_v0_agent_raw_for_catalog(raw, console_host=console_host)
    status = normalized.get("status")
    if status in _V1_AGENT_STATUSES:
        pass
    elif status is not None:
        normalized["status"] = "ACTIVE"
    else:
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


async def upsert_raw_entity(
    kind: str,
    raw: dict[str, Any],
    *,
    console_host: str | None = None,
) -> None:
    await ocean.integration.port_app_config_handler.get_port_app_config(use_cache=False)
    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
        await ocean.register_raw(
            kind, [normalize_raw_for_catalog(kind, raw, console_host=console_host)]
        )


async def try_upsert_entity(
    kind: str,
    raw: dict[str, Any],
    *,
    console_host: str | None = None,
) -> None:
    try:
        await upsert_raw_entity(kind, raw, console_host=console_host)
    except Exception as error:
        logger.warning(
            f"Failed to upsert {kind} into the catalog (continuing): {error}"
        )


async def fetch_usage_by_run_id(
    client: CursorAgentsClient, agent_id: str
) -> dict[str, Any]:
    try:
        usage_response = await client.send_api_request("GET", v1_agent_usage(agent_id))
    except Exception as error:
        logger.warning(
            f"Failed to fetch token usage for Cursor agent {agent_id} "
            f"(runs will sync without usage): {error}"
        )
        return {}
    runs = usage_response.get("runs")
    if not isinstance(runs, list):
        return {}

    usage_by_run_id: dict[str, Any] = {}
    for run_usage in runs:
        if not isinstance(run_usage, dict):
            continue
        run_id = run_usage.get("id")
        usage = run_usage.get("usage")
        if isinstance(run_id, str) and run_id and usage is not None:
            usage_by_run_id[run_id] = usage
    return usage_by_run_id


async def fetch_run_raw_for_catalog(
    client: CursorAgentsClient,
    agent_id: str,
    run_id: str,
    *,
    status: str | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    async def fetch_run_or_fallback() -> dict[str, Any]:
        try:
            return dict(
                await client.send_api_request("GET", v1_agent_run(agent_id, run_id))
            )
        except Exception as error:
            logger.warning(
                f"Failed to fetch Cursor run {run_id} for agent {agent_id} "
                f"(using webhook snapshot): {error}"
            )
            return {"id": run_id}

    run_raw, usage_by_run_id = await asyncio.gather(
        fetch_run_or_fallback(),
        fetch_usage_by_run_id(client, agent_id),
    )
    run_raw.setdefault("agentId", agent_id)
    if status is not None:
        run_raw.setdefault("status", status)
    if updated_at is not None:
        run_raw.setdefault("updatedAt", format_datetime_for_catalog(updated_at))
    usage = usage_by_run_id.get(run_id)
    if usage is not None:
        run_raw["usage"] = usage
    return run_raw
