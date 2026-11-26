from __future__ import annotations

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.core.exporters.endpoint_scoped_exporter import (
    EndpointScopedExporter,
)
from azure_integration.foundry.core.options import (
    ListConversationsOptions,
    SingleConversationOptions,
)
from azure_integration.foundry.foundry_incremental import CONVERSATION_INCREMENTAL
from azure_integration.foundry.helpers.conversation_overlay import enrich_conversation_pages


class ConversationsExporter(
    EndpointScopedExporter[ListConversationsOptions, SingleConversationOptions]
):
    """Conversations via agent protocol and/or project openai/v1 list APIs."""

    resource = "conversations"
    strategy = CONVERSATION_INCREMENTAL

    async def get_paginated_resources(
        self, options: ListConversationsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        since_days = options.since_days if options.since_days is not None else 30
        pages = EndpointScopedExporter.get_paginated_resources(self, options)
        async for page in enrich_conversation_pages(
            self.client, since_days=since_days, pages=pages
        ):
            yield page
