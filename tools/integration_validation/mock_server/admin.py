"""Admin API routes for the integration-validation mock server."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tools.integration_validation.mock_server.constants import ADMIN_PREFIX
from tools.integration_validation.mock_server.exceptions import RouteFileLoadError
from tools.integration_validation.mock_server.loader import load_route_files
from tools.integration_validation.mock_server.request_handler import (
    resolve_fixture_path,
)
from tools.integration_validation.mock_server.schemas import (
    JournalEntry,
    JournalResponse,
    LoadScenarioRequest,
    LoadScenarioResponse,
    ResetResponse,
    RouteUsage,
)
from tools.integration_validation.mock_server.state import MockServerState


def build_admin_router(state: MockServerState) -> APIRouter:
    router = APIRouter()

    @router.post(f"{ADMIN_PREFIX}/scenario", response_model=LoadScenarioResponse)
    async def load_scenario(payload: LoadScenarioRequest) -> LoadScenarioResponse:
        root = state.fixture_root
        try:
            route_files = [
                resolve_fixture_path(root, route_file) for route_file in payload.routes
            ]
            routes = load_route_files(route_files)
        except (RouteFileLoadError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        async with state.lock:
            state.load_routes(routes)
        return LoadScenarioResponse(route_ids=[route.id for route in routes])

    @router.get(f"{ADMIN_PREFIX}/journal", response_model=JournalResponse)
    async def get_journal() -> JournalResponse:
        async with state.lock:
            return JournalResponse(
                requests=list(state.journal),
                route_call_counts=dict(state.route_call_counts),
            )

    @router.get(f"{ADMIN_PREFIX}/unmatched", response_model=list[JournalEntry])
    async def get_unmatched() -> list[JournalEntry]:
        async with state.lock:
            return [entry for entry in state.journal if entry.matched_route_id is None]

    @router.get(f"{ADMIN_PREFIX}/unused", response_model=list[RouteUsage])
    async def get_unused() -> list[RouteUsage]:
        async with state.lock:
            return [
                RouteUsage(route_id=route.id, call_count=0)
                for route in state.routes
                if state.route_call_counts.get(route.id, 0) == 0
            ]

    @router.post(f"{ADMIN_PREFIX}/reset", response_model=ResetResponse)
    async def reset() -> ResetResponse:
        async with state.lock:
            state.reset()
        return ResetResponse()

    return router
