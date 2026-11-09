from __future__ import annotations

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListConversationsOptions
from azure_integration.foundry.foundry_incremental import CONVERSATION_INCREMENTAL
from azure_integration.foundry.helpers.utils import (
    effective_conversation_cutoff,
    enrich_with_project,
)


class ConversationsExporter:
    """OpenAI-style conversation index (metadata only)."""

    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: ListConversationsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        since_days = options.since_days
        incremental_cursor = active_incremental_cursor()
        cutoff = effective_conversation_cutoff(
            incremental_cursor, since_days=since_days
        )
        # order=desc always (API sorts by created_at); cutoff may be sinceDays-only.
        params = CONVERSATION_INCREMENTAL.merge_params({}, cutoff)

        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "openai/v1/conversations",
                params=params,
            ),
            cursor=cutoff,
            strategy=CONVERSATION_INCREMENTAL,
        ):
            yield [
                enrich_with_project(
                    item,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
