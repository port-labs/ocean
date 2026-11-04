from __future__ import annotations

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.http.foundry_client import FoundryHttpClient
from clients.quota_client import create_quota_client
from core.exporters.abstract_exporter import AbstractFoundryExporter
from helpers.conversation_sync import effective_conversation_cutoff
from helpers.project_scope import enrich_with_project, get_project_endpoint
from helpers.utils import region_from_project_endpoint, timestamp_to_iso
from foundry_incremental import CONVERSATION_INCREMENTAL


class ConversationsExporter(AbstractFoundryExporter[FoundryHttpClient]):
    """OpenAI-style conversation index (metadata; rollups refreshed by response sync)."""

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
        quota = create_quota_client()
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
            check = await quota.check_before_batch(
                region=region_from_project_endpoint(project_endpoint),
                batch_size=len(page),
            )
            if not check.allowed:
                logger.warning(
                    f"Skipping conversation batch for {project_endpoint}: {check.message}"
                )
                continue
            batch = [
                enrich_with_project(_normalize_conversation(item)) for item in page
            ]
            if batch:
                yield batch


def _normalize_conversation(item: dict[str, object]) -> dict[str, object]:
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
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "tool_call_count",
        "participant_agent_ids",
        "participant_model_deployment_ids",
    ):
        if key in item:
            normalized[key] = item[key]
    return normalized
