from __future__ import annotations

from typing import Any

from loguru import logger

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.helpers.utils import agent_openai_protocol_path


def _conversations_base(agent_id: str | None) -> str:
    if agent_id:
        return agent_openai_protocol_path(agent_id, "conversations")
    return "openai/v1/conversations"


async def resolve_conversation_for_invoke(
    client: FoundryHttpClient,
    *,
    project_endpoint: str,
    conversation_id: str | None,
    metadata: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> str:
    """Return a conversation id for invoke; create one when missing or not found.

    Agent invokes use the agent OpenAI protocol conversation store; model
    invokes use project ``openai/v1/conversations``.
    """
    conversation_id = (conversation_id or "").strip() or None
    base = _conversations_base(agent_id)

    async def _create() -> str:
        url = client.build_url(project_endpoint, base)
        body: dict[str, Any] = {}
        if metadata:
            body["metadata"] = metadata
        created = await client.send_api_request(url, method="POST", json_body=body)
        if isinstance(created, dict) and created.get("id"):
            return str(created["id"])
        raise RuntimeError("Unexpected create conversation response")

    if not conversation_id:
        return await _create()

    url = client.build_url(project_endpoint, f"{base}/{conversation_id}")
    existing = await client.send_api_request(url, method="GET")
    if not (isinstance(existing, dict) and existing.get("id")):
        logger.warning(
            f"Conversation {conversation_id} not found under {base}; creating a new one"
        )
        return await _create()

    resolved = str(existing["id"])
    if metadata:
        try:
            await client.send_api_request(
                url, method="POST", json_body={"metadata": metadata}
            )
        except Exception as error:
            logger.warning(
                f"Failed to update conversation {resolved} metadata: {error}"
            )
    return resolved
