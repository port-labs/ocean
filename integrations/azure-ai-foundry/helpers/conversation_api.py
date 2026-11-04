from __future__ import annotations

from typing import Any

from loguru import logger

from clients.http.foundry_client import FoundryHttpClient
from helpers.project_scope import get_project_endpoint


async def resolve_conversation_for_invoke(
    client: FoundryHttpClient,
    *,
    conversation_id: str | None,
    metadata: dict[str, Any] | None,
) -> str | None:
    """Create or patch conversation metadata before a Responses invoke."""
    if not metadata:
        return conversation_id
    project_endpoint = get_project_endpoint()
    if conversation_id:
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
    try:
        created = await client.send_api_request(
            url, method="POST", json_body={"metadata": metadata}
        )
    except Exception as error:
        logger.warning(f"Failed to create conversation with metadata: {error}")
        return conversation_id
    if isinstance(created, dict) and created.get("id"):
        return str(created["id"])
    return conversation_id
