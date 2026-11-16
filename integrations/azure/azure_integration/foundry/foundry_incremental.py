"""Incremental sync strategies for Azure AI Foundry resources."""

from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ClientSideCutoffStrategy

from azure_integration.foundry.helpers.utils import parse_foundry_timestamp

# Foundry list APIs that accept ``order`` sort by ``created_at`` only (not updated_at).
_ORDER_DESC = {"order": "desc"}


class FoundryClientSideCutoffStrategy(ClientSideCutoffStrategy):
    """Client-side cutoff for Foundry lists that support ``order=desc`` by created_at."""

    def build_params(self, cursor: datetime | None) -> dict[str, Any]:
        # Always request newest-first. Cutoff may come from sinceDays with no watermark.
        del cursor
        return dict(self._query_params)

    def should_stop(self, item: dict[str, Any], cursor: datetime | None) -> bool:
        if cursor is None:
            return False
        raw = item.get(self._stop_field)
        if not raw:
            parts = self._stop_field.split("_")
            camel = parts[0] + "".join(part.title() for part in parts[1:])
            raw = item.get(camel)
        if not raw and self._stop_field == "created_at":
            # Agents expose created_at on versions.latest when not top-level.
            versions = item.get("versions")
            if isinstance(versions, dict):
                latest = versions.get("latest")
                if isinstance(latest, dict):
                    raw = latest.get("created_at") or latest.get("createdAt")
        if not raw:
            return False
        item_time = parse_foundry_timestamp(raw)
        if item_time is None:
            return False
        return item_time < cursor


def _created_at_desc() -> FoundryClientSideCutoffStrategy:
    return FoundryClientSideCutoffStrategy(
        stop_field="created_at", query_params=dict(_ORDER_DESC)
    )


# order=desc + created_at: agents, conversations, responses, memory stores.
AGENT_INCREMENTAL = _created_at_desc()
CONVERSATION_INCREMENTAL = _created_at_desc()
RESPONSE_INCREMENTAL = _created_at_desc()
MEMORY_STORE_INCREMENTAL = _created_at_desc()

# Deployments list has no ``order`` param and no timestamps — always full scan.
MODEL_DEPLOYMENT_INCREMENTAL = None
