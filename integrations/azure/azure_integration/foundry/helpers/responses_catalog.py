from __future__ import annotations

from typing import Any

from azure_integration.foundry.helpers.utils import timestamp_to_iso


def merge_usage_into_row(row: dict[str, Any], usage: dict[str, Any]) -> None:
    prompt = usage.get("prompt_tokens")
    if prompt is None:
        prompt = usage.get("input_tokens")
    completion = usage.get("completion_tokens")
    if completion is None:
        completion = usage.get("output_tokens")
    total = usage.get("total_tokens")
    if prompt is not None:
        row["prompt_tokens"] = int(prompt)
    if completion is not None:
        row["completion_tokens"] = int(completion)
    if total is not None:
        row["total_tokens"] = int(total)
    elif prompt is not None and completion is not None:
        row["total_tokens"] = int(prompt) + int(completion)


def count_tool_calls_in_response(response: dict[str, Any]) -> int:
    output = response.get("output")
    if not isinstance(output, list):
        return 0
    tool_types = {
        "function_call",
        "mcp_call",
        "tool_call",
        "code_interpreter_call",
        "file_search_call",
        "web_search_call",
    }
    return sum(
        1
        for item in output
        if isinstance(item, dict) and str(item.get("type") or "") in tool_types
    )


def conversation_id_from_response(response: dict[str, Any]) -> str | None:
    for key in ("conversation_id", "conversationId"):
        value = response.get(key)
        if value:
            return str(value)
    conversation = response.get("conversation")
    if isinstance(conversation, dict) and conversation.get("id"):
        return str(conversation["id"])
    if isinstance(conversation, str) and conversation:
        return conversation
    return None


def conversation_row_from_response(
    response: dict[str, Any],
    *,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    conversation_id = conversation_id_from_response(response)
    if not conversation_id:
        return None
    row: dict[str, Any] = {"id": conversation_id}
    if agent_id:
        catalog_id = agent_id.split(":", 1)[0] if ":" in agent_id else agent_id
        row["participant_agent_ids"] = [catalog_id]
    usage = response.get("usage")
    if isinstance(usage, dict):
        merge_usage_into_row(row, usage)
    tool_calls = count_tool_calls_in_response(response)
    if tool_calls:
        row["tool_call_count"] = tool_calls
    return row


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
