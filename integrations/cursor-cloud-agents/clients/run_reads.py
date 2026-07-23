from __future__ import annotations

from typing import Any

from clients.cursor_agents_client import CursorAgentsClient
from clients.endpoints import v1_agent_runs


async def list_first_runs_page(
    client: CursorAgentsClient, agent_id: str
) -> list[dict[str, Any]]:
    """First page of runs for an agent (newest first per Cursor API docs)."""
    payload = await client.send_api_request(
        "GET",
        v1_agent_runs(agent_id),
        params={"limit": client.page_size},
    )
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return items
