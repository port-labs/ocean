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
    """OpenAI-style conversation index (metadata; rollups refreshed by response sync)."""

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
        params = CONVERSATION_INCREMENTAL.merge_params({}, incremental_cursor)

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
                enrich_with_project(
                    dict(item),
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if batch:
                yield batch
