"""Incremental sync strategies for Azure AI Foundry resources."""

from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy

from azure_integration.foundry.helpers.utils import parse_foundry_timestamp


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


def _cutoff(stop_field: str) -> FoundryClientSideCutoffStrategy:
    return FoundryClientSideCutoffStrategy(
        stop_field=stop_field, query_params={"order": "desc"}
    )


AGENT_INCREMENTAL = _cutoff("updated_at")
CONVERSATION_INCREMENTAL = _cutoff("created_at")
RESPONSE_INCREMENTAL = _cutoff("created_at")
MODEL_DEPLOYMENT_INCREMENTAL = _cutoff("updated_at")
MEMORY_STORE_INCREMENTAL = _cutoff("created_at")
