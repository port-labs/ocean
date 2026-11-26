from __future__ import annotations

from azure_integration.foundry.clients.http.foundry_client import (
    FoundryApiError,
    FoundryHttpClient,
)
from azure_integration.foundry.helpers.utils import agent_openai_protocol_path
from azure_integration.foundry.models.responses import Response
from pydantic import ValidationError

_TERMINAL_RESPONSE_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "incomplete", "canceled"}
)


def _is_in_progress(status: str | None) -> bool:
    if not status:
        return True
    return status.casefold() not in _TERMINAL_RESPONSE_STATUSES


async def in_progress_response_ids_for_conversation(
    client: FoundryHttpClient,
    *,
    project_endpoint: str,
    conversation_id: str,
    agent_id: str | None = None,
) -> list[str]:
    """All non-terminal response ids for a conversation (newest pages first)."""
    paths = (
        [agent_openai_protocol_path(agent_id, "responses")]
        if agent_id
        else ["openai/v1/responses"]
    )
    params = {"limit": FoundryHttpClient.PAGE_SIZE, "order": "desc"}
    found: list[str] = []
    seen: set[str] = set()

    for path in paths:
        try:
            pages = client.send_cursor_paginated_request(
                project_endpoint,
                path,
                params=params,
            )
            async for page in pages:
                for raw in page:
                    if not isinstance(raw, dict):
                        continue
                    try:
                        response = Response.model_validate(raw)
                    except ValidationError:
                        continue
                    if response.resolved_conversation_id() != conversation_id:
                        continue
                    if not response.id or not _is_in_progress(response.status):
                        continue
                    if response.id in seen:
                        continue
                    seen.add(response.id)
                    found.append(response.id)
        except FoundryApiError:
            continue
    return found
