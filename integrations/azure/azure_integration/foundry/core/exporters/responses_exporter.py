from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListResponsesOptions
from azure_integration.foundry.foundry_incremental import (
    CONVERSATION_INCREMENTAL,
    RESPONSE_INCREMENTAL,
)
from azure_integration.foundry.helpers.responses_catalog import (
    merge_response_into_conversation_rollup,
    normalize_foundry_response,
)
from azure_integration.foundry.helpers.utils import (
    effective_conversation_cutoff,
    enrich_with_project,
    timestamp_to_iso,
)
from azure_integration.foundry.kinds import ObjectKind


class ResponsesExporter:
    """Foundry Responses API objects, related to conversations with rollup refresh."""

    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: ListResponsesOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        since_days = options.since_days
        response_cursor = active_incremental_cursor()
        response_cutoff = effective_conversation_cutoff(
            response_cursor, since_days=since_days
        )
        conversation_cutoff = effective_conversation_cutoff(None, since_days=since_days)
        conv_params = CONVERSATION_INCREMENTAL.merge_params({}, None)

        async for conv_page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "openai/v1/conversations",
                params=conv_params,
            ),
            cursor=conversation_cutoff,
            strategy=CONVERSATION_INCREMENTAL,
        ):
            responses_batch: list[dict[str, object]] = []
            rollups_to_register: list[dict[str, object]] = []

            for conversation in conv_page:
                conversation_id = conversation.get("id")
                if not isinstance(conversation_id, str) or not conversation_id:
                    continue
                response_params = RESPONSE_INCREMENTAL.merge_params(
                    {"order": "desc", "conversation_id": conversation_id},
                    response_cursor,
                )
                touched = False

                async for response_page in paginate_with_strategy(
                    self.client.send_cursor_paginated_request(
                        project_endpoint,
                        "openai/v1/responses",
                        params=response_params,
                    ),
                    cursor=response_cutoff,
                    strategy=RESPONSE_INCREMENTAL,
                ):
                    for source in response_page:
                        if not source.get("id"):
                            continue
                        touched = True
                        responses_batch.append(
                            enrich_with_project(
                                dict(source),
                                project_endpoint=project_endpoint,
                                project_id=project_id,
                            )
                        )

                if touched:
                    rollups_to_register.append(
                        await _build_conversation_rollup(
                            self.client,
                            project_endpoint=project_endpoint,
                            conversation_id=conversation_id,
                            conversation_list_row=conversation,
                        )
                    )

            if responses_batch:
                yield responses_batch
                await _register_conversation_rollups(
                    rollups_to_register,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )


async def _build_conversation_rollup(
    client: FoundryHttpClient,
    *,
    project_endpoint: str,
    conversation_id: str,
    conversation_list_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
            merge_response_into_conversation_rollup(rollup, response_row, source=source)
    rollup.setdefault("prompt_tokens", 0)
    rollup.setdefault("completion_tokens", 0)
    rollup.setdefault("total_tokens", 0)
    rollup.setdefault("participant_agent_ids", [])
    rollup.setdefault("participant_model_deployment_ids", [])
    return rollup


async def _register_conversation_rollups(
    raw_rows: list[dict[str, Any]],
    *,
    project_endpoint: str,
    project_id: str,
) -> None:
    if not raw_rows:
        return
    try:
        batch = [
            enrich_with_project(
                dict(row),
                project_endpoint=project_endpoint,
                project_id=project_id,
            )
            for row in raw_rows
        ]
        await ocean.register_raw(ObjectKind.CONVERSATION, batch)
    except Exception as error:
        logger.warning(
            f"Failed to upsert {len(raw_rows)} conversation rollup(s): {error}"
        )
