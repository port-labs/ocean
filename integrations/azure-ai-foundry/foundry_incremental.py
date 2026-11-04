"""Incremental sync strategies for Azure AI Foundry Agent Service resources."""

from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy

from helpers.utils import parse_foundry_timestamp


class FoundryClientSideCutoffStrategy(ClientSideCutoffStrategy):
    """Client-side cutoff that accepts Foundry Unix epoch and ISO timestamps."""

    def should_stop(self, item: dict[str, Any], cursor: datetime | None) -> bool:
        if cursor is None:
            return False
        raw = item.get(self._stop_field)
        if not raw:
            return False
        item_time = parse_foundry_timestamp(raw)
        if item_time is None:
            return False
        return item_time < cursor


AGENT_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"order": "desc"},
)

AGENT_VERSION_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="created_at",
    query_params={"order": "desc"},
)

CONVERSATION_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="created_at",
    query_params={"order": "desc"},
)

RESPONSE_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="created_at",
    query_params={"order": "desc"},
)

MODEL_DEPLOYMENT_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"order": "desc"},
)

SKILL_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="updated_at",
    query_params={"order": "desc"},
)

MEMORY_STORE_INCREMENTAL = FoundryClientSideCutoffStrategy(
    stop_field="created_at",
    query_params={"order": "desc"},
)
