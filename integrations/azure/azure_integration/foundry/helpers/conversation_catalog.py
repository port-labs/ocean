from __future__ import annotations

from typing import Any

from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.helpers.usage_metrics import (
    count_tool_calls_in_response,
    merge_usage_into_row,
)
from azure_integration.foundry.kinds import ObjectKind


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


async def register_catalog_conversation(
    row: dict[str, Any], run: IntegrationRun
) -> None:
    from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor

    await AbstractFoundryExecutor().register_entity(ObjectKind.CONVERSATION, row, run)
