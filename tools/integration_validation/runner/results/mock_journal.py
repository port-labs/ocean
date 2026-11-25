"""Read-only client for the mock server's admin journal."""

from __future__ import annotations

from typing import Any

import httpx

from tools.integration_validation.mock_server.admin_schemas import (
    JournalEntry,
    JournalResponse,
)
from tools.integration_validation.mock_server.constants import ADMIN_PREFIX
from tools.integration_validation.runner.core.errors import ValidationSetupError

MOCK_ADMIN_TIMEOUT_SECONDS = 10.0


class MockJournal(JournalResponse):
    """Every request since the developer last loaded or reset the mock."""

    @property
    def unmatched_requests(self) -> list[JournalEntry]:
        return [entry for entry in self.requests if entry.matched_route_id is None]

    @property
    def unused_route_ids(self) -> list[str]:
        return [
            route_id for route_id, count in self.route_call_counts.items() if not count
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_count": len(self.requests),
            "unmatched_requests": [
                {"method": entry.method, "path": entry.path, "query": entry.query}
                for entry in self.unmatched_requests
            ],
            "unused_routes": self.unused_route_ids,
            "route_call_counts": self.route_call_counts,
        }


async def fetch_mock_journal(
    mock_base_url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MockJournal:
    url = f"{mock_base_url.rstrip('/')}{ADMIN_PREFIX}/journal"
    try:
        async with httpx.AsyncClient(
            timeout=MOCK_ADMIN_TIMEOUT_SECONDS, transport=transport
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValidationSetupError(
            f"Could not read the mock server journal at {url}: {exc}. "
            "Is the mock server running at --mock-base-url?"
        ) from exc
    try:
        return MockJournal.model_validate_json(response.content)
    except ValueError as exc:
        raise ValidationSetupError(
            f"Mock server at {url} returned an unexpected journal: {exc}"
        ) from exc
