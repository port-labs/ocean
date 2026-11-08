from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.helpers.catalog_sync import normalize_catalog_payload
from azure_integration.foundry.helpers.project_scope import enrich_with_project
from azure_integration.foundry.helpers.responses_catalog import (
    merge_response_into_conversation_rollup,
    normalize_foundry_response,
)
from azure_integration.foundry.helpers.utils import timestamp_to_iso
from azure_integration.foundry.kinds import ObjectKind


async def build_conversation_rollup(
    client: FoundryHttpClient,
    *,
    project_endpoint: str,
    conversation_id: str,
    conversation_list_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate metrics and participants from all responses in a conversation."""
    rollup: dict[str, Any] = {"id": conversation_id}
    if conversation_list_row:
        created_iso = timestamp_to_iso(
            conversation_list_row.get("created_at")
            or conversation_list_row.get("createdAt")
        )
        if created_iso:
            rollup["created_at"] = created_iso
        metadata = conversation_list_row.get("metadata")
        if isinstance(metadata, dict):
            rollup["metadata"] = metadata
    params: dict[str, Any] = {"order": "asc", "conversation_id": conversation_id}
    async for page in client.send_cursor_paginated_request(
        project_endpoint,
        "openai/v1/responses",
        params=params,
    ):
        for source in page:
            response_row = normalize_foundry_response(source)
            if not response_row:
                continue
            merge_response_into_conversation_rollup(
                rollup, response_row, source=source
            )
    rollup.setdefault("prompt_tokens", 0)
    rollup.setdefault("completion_tokens", 0)
    rollup.setdefault("total_tokens", 0)
    rollup.setdefault("participant_agent_ids", [])
    rollup.setdefault("participant_model_deployment_ids", [])
    return rollup


async def register_conversation_rollups(raw_rows: list[dict[str, Any]]) -> None:
    if not raw_rows:
        return
    try:
        batch = [
            enrich_with_project(
                normalize_catalog_payload(ObjectKind.CONVERSATION, dict(row))
            )
            for row in raw_rows
        ]
        await ocean.register_raw(ObjectKind.CONVERSATION, batch)
    except Exception as error:
        logger.warning(
            f"Failed to upsert {len(raw_rows)} conversation rollup(s): {error}"
        )
