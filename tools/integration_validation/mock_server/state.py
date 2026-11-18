"""In-memory state for the integration-validation mock server."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from tools.integration_validation.mock_server.models import MockRoute
from tools.integration_validation.mock_server.responder import ResponseRenderer
from tools.integration_validation.mock_server.schemas import JournalEntry


@dataclass
class MockServerState:
    fixture_root: Path
    renderer: ResponseRenderer
    routes: list[MockRoute] = field(default_factory=list)
    journal: list[JournalEntry] = field(default_factory=list)
    route_call_counts: dict[str, int] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def load_routes(self, routes: list[MockRoute]) -> None:
        self.routes = routes
        self.reset()

    def reset(self) -> None:
        self.journal.clear()
        self.route_call_counts = {route.id: 0 for route in self.routes}
        self.renderer.reset()
