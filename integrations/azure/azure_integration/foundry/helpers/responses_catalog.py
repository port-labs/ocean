from __future__ import annotations

from typing import Any

from azure_integration.foundry.helpers.conversation_catalog import (
    conversation_id_from_response,
)
from azure_integration.foundry.helpers.usage_metrics import (
    add_usage_rows,
    count_tool_calls_in_response,
    merge_usage_into_row,
)
from azure_integration.foundry.helpers.utils import timestamp_to_iso


def catalog_agent_id(raw: str) -> str:
    if ":" in raw:
        return raw.split(":", 1)[0]
    return raw


def agent_id_from_response(response: dict[str, Any]) -> str | None:
    agent_ref = response.get("agent")
    if isinstance(agent_ref, dict):
        for key in ("name", "id"):
            value = agent_ref.get(key)
            if value:
                return catalog_agent_id(str(value))
    for key in ("agent_id", "agentId", "agent_name", "agentName"):
        value = response.get(key)
        if value:
            return catalog_agent_id(str(value))
    metadata = response.get("metadata")
    if isinstance(metadata, dict):
        for key in ("agent", "agent_id", "agentId", "agent_name", "agentName"):
            value = metadata.get(key)
            if value:
                return catalog_agent_id(str(value))
    return None


def model_deployment_id_from_response(response: dict[str, Any]) -> str | None:
    direct = response.get("model_deployment_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    model = response.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def normalize_foundry_response(source: dict[str, Any]) -> dict[str, Any] | None:
    response_id = source.get("id")
    if not response_id:
        return None
    row: dict[str, Any] = {"id": str(response_id)}
    conversation_id = conversation_id_from_response(source)
    if conversation_id:
        row["conversation_id"] = conversation_id
    status = source.get("status")
    if isinstance(status, str):
        row["status"] = status
    created_iso = timestamp_to_iso(source.get("created_at") or source.get("createdAt"))
    if created_iso:
        row["created_at"] = created_iso
    usage = source.get("usage")
    if isinstance(usage, dict):
        merge_usage_into_row(row, usage)
    else:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = source.get(key)
            if value is not None and key not in row:
                row[key] = int(value)
    tool_calls = count_tool_calls_in_response(source)
    if tool_calls:
        row["tool_call_count"] = tool_calls
    agent_id = agent_id_from_response(source)
    if agent_id:
        row["agent_id"] = agent_id
    model_id = model_deployment_id_from_response(source)
    if model_id:
        row["model_deployment_id"] = model_id
    return row


def merge_response_into_conversation_rollup(
    rollup: dict[str, Any], response_row: dict[str, Any], *, source: dict[str, Any]
) -> None:
    totals: dict[str, int] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "tool_call_count": 0,
    }
    add_usage_rows(totals, source.get("usage"))
    totals["tool_call_count"] = count_tool_calls_in_response(source)
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "tool_call_count",
    ):
        delta = int(totals.get(key) or 0)
        if delta:
            rollup[key] = int(rollup.get(key) or 0) + delta
    agents = rollup.setdefault("participant_agent_ids", [])
    agent_id = response_row.get("agent_id")
    if isinstance(agent_id, str) and agent_id and agent_id not in agents:
        agents.append(agent_id)
    models = rollup.setdefault("participant_model_deployment_ids", [])
    model_id = response_row.get("model_deployment_id")
    if isinstance(model_id, str) and model_id and model_id not in models:
        models.append(model_id)
