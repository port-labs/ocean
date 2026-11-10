from __future__ import annotations

from typing import Any

from loguru import logger

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.helpers.scope import get_project_endpoint


async def resolve_conversation_for_invoke(
    client: FoundryHttpClient,
    *,
    conversation_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Return a conversation id for invoke; create one when missing."""
    project_endpoint = get_project_endpoint()
    if conversation_id:
        if metadata:
            url = client.build_url(
                project_endpoint, f"openai/v1/conversations/{conversation_id}"
            )
            try:
                await client.send_api_request(
                    url,
                    method="POST",
                    json_body={"metadata": metadata},
                )
            except Exception as error:
                logger.warning(
                    f"Failed to update conversation {conversation_id} metadata: {error}"
                )
        return conversation_id

    url = client.build_url(project_endpoint, "openai/v1/conversations")
    body: dict[str, Any] = {}
    if metadata:
        body["metadata"] = metadata
    created = await client.send_api_request(url, method="POST", json_body=body)
    if isinstance(created, dict) and created.get("id"):
        return str(created["id"])
    raise RuntimeError("Unexpected create conversation response")
