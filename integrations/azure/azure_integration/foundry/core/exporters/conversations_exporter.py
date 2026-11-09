from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.foundry_incremental import CONVERSATION_INCREMENTAL
from azure_integration.foundry.helpers.project_scope import (
    enrich_with_project,
    get_project_endpoint,
)
from azure_integration.foundry.helpers.utils import (
    effective_conversation_cutoff,
    timestamp_to_iso,
)


class ConversationsExporter:
    """OpenAI-style conversation index (metadata; rollups refreshed by response sync)."""

    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self,
        *,
        since_days: int | None = 365,
        **_options: object,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        incremental_cursor = active_incremental_cursor()
        cutoff = effective_conversation_cutoff(
            incremental_cursor, since_days=since_days
        )
        params = CONVERSATION_INCREMENTAL.merge_params({}, incremental_cursor)
        project_endpoint = get_project_endpoint()

        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "openai/v1/conversations",
                params=params,
            ),
            cursor=cutoff,
            strategy=CONVERSATION_INCREMENTAL,
        ):
            batch = [
                enrich_with_project(_normalize_conversation(item)) for item in page
            ]
            if batch:
                yield batch


def _normalize_conversation(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    conversation_id = item.get("id")
    if conversation_id is not None:
        normalized["id"] = conversation_id
    created_iso = timestamp_to_iso(item.get("created_at") or item.get("createdAt"))
    if created_iso:
        normalized["created_at"] = created_iso
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        normalized["metadata"] = metadata
    normalized["prompt_tokens"] = int(item.get("prompt_tokens") or 0)
    normalized["completion_tokens"] = int(item.get("completion_tokens") or 0)
    normalized["total_tokens"] = int(item.get("total_tokens") or 0)
    if item.get("tool_call_count") is not None:
        normalized["tool_call_count"] = int(item["tool_call_count"])
    agents = item.get("participant_agent_ids")
    normalized["participant_agent_ids"] = (
        list(agents) if isinstance(agents, list) else []
    )
    models = item.get("participant_model_deployment_ids")
    normalized["participant_model_deployment_ids"] = (
        list(models) if isinstance(models, list) else []
    )
    return normalized
