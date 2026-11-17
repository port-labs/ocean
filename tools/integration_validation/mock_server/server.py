"""FastAPI application for the integration-validation mock server."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from tools.integration_validation.mock_server.exceptions import (
    ResponseRenderError,
    RouteFileLoadError,
)
from tools.integration_validation.mock_server.loader import load_route_files
from tools.integration_validation.mock_server.matcher import match_route
from tools.integration_validation.mock_server.models import MockRoute
from tools.integration_validation.mock_server.responder import ResponseRenderer

MOCK_SERVER_HOST = "127.0.0.1"
MOCK_SERVER_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class LoadScenarioRequest(BaseModel):
    """Route files to activate, relative to the mock fixture root."""

    model_config = ConfigDict(extra="forbid")

    routes: list[str] = Field(..., min_length=1)


class LoadScenarioResponse(BaseModel):
    route_ids: list[str]


class JournalEntry(BaseModel):
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: Any = None
    matched_route_id: str | None
    response_status: int


class JournalResponse(BaseModel):
    requests: list[JournalEntry]
    route_call_counts: dict[str, int]


class RouteUsage(BaseModel):
    route_id: str
    call_count: int


class ResetResponse(BaseModel):
    status: str = "reset"


@dataclass
class _MockServerState:
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


def create_mock_server_app(fixture_root: Path | str) -> FastAPI:
    """Create a mock-server app rooted at an integration's ``mock`` directory."""
    root = Path(fixture_root).resolve()
    state = _MockServerState(
        fixture_root=root,
        renderer=ResponseRenderer(root),
    )
    app = FastAPI(title="Ocean Integration Validation Mock Server")

    @app.post(
        "/__admin/scenario",
        response_model=LoadScenarioResponse,
    )
    async def load_scenario(payload: LoadScenarioRequest) -> LoadScenarioResponse:
        try:
            route_files = [
                _resolve_fixture_path(root, route_file) for route_file in payload.routes
            ]
            routes = load_route_files(route_files)
        except (RouteFileLoadError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        async with state.lock:
            state.load_routes(routes)
        return LoadScenarioResponse(route_ids=[route.id for route in routes])

    @app.get(
        "/__admin/journal",
        response_model=JournalResponse,
    )
    async def get_journal() -> JournalResponse:
        async with state.lock:
            return JournalResponse(
                requests=list(state.journal),
                route_call_counts=dict(state.route_call_counts),
            )

    @app.get(
        "/__admin/unmatched",
        response_model=list[JournalEntry],
    )
    async def get_unmatched() -> list[JournalEntry]:
        async with state.lock:
            return [entry for entry in state.journal if entry.matched_route_id is None]

    @app.get(
        "/__admin/unused",
        response_model=list[RouteUsage],
    )
    async def get_unused() -> list[RouteUsage]:
        async with state.lock:
            return [
                RouteUsage(route_id=route.id, call_count=0)
                for route in state.routes
                if state.route_call_counts.get(route.id, 0) == 0
            ]

    @app.post(
        "/__admin/reset",
        response_model=ResetResponse,
    )
    async def reset() -> ResetResponse:
        async with state.lock:
            state.reset()
        return ResetResponse()

    @app.api_route("/{request_path:path}", methods=MOCK_SERVER_METHODS)
    async def handle_mock_request(request: Request, request_path: str) -> Response:
        del request_path
        body = await _read_request_body(request)
        query = dict(request.query_params)
        headers = dict(request.headers)

        async with state.lock:
            route_match = match_route(
                state.routes,
                method=request.method,
                path=request.url.path,
                query=query,
                headers=headers,
                body=body,
            )
            if route_match is None:
                entry = _journal_entry(
                    request=request,
                    query=query,
                    headers=headers,
                    body=body,
                    matched_route_id=None,
                    response_status=599,
                )
                state.journal.append(entry)
                return JSONResponse(
                    status_code=599,
                    content={
                        "error": "unmatched_request",
                        "message": (
                            f"No mock route matched "
                            f"{request.method} {request.url.path}"
                        ),
                        "request": {
                            "method": request.method,
                            "path": request.url.path,
                            "query": query,
                        },
                    },
                )

            route_id = route_match.route.id
            state.route_call_counts[route_id] = (
                state.route_call_counts.get(route_id, 0) + 1
            )
            try:
                rendered = state.renderer.render(route_match)
            except ResponseRenderError as exc:
                state.journal.append(
                    _journal_entry(
                        request=request,
                        query=query,
                        headers=headers,
                        body=body,
                        matched_route_id=route_id,
                        response_status=500,
                    )
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "response_render_error",
                        "message": str(exc),
                        "route_id": route_id,
                    },
                )

            state.journal.append(
                _journal_entry(
                    request=request,
                    query=query,
                    headers=headers,
                    body=body,
                    matched_route_id=route_id,
                    response_status=rendered.status,
                )
            )

        if rendered.body is None:
            return Response(
                status_code=rendered.status,
                headers=rendered.headers,
            )
        return JSONResponse(
            status_code=rendered.status,
            headers=rendered.headers,
            content=rendered.body,
        )

    return app


def run_mock_server(fixture_root: Path | str, port: int) -> None:
    """Run the mock server on loopback only."""
    uvicorn.run(
        create_mock_server_app(fixture_root),
        host=MOCK_SERVER_HOST,
        port=port,
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the Ocean integration-validation mock server."
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        required=True,
        help="Path to the integration's tests/validation/mock directory.",
    )
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args(argv)
    run_mock_server(args.fixture_root, args.port)


def _resolve_fixture_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Route file '{relative_path}' escapes fixture root '{root}'"
        ) from exc
    return path


async def _read_request_body(request: Request) -> Any:
    raw_body = await request.body()
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw_body.decode("utf-8", errors="replace")


def _journal_entry(
    *,
    request: Request,
    query: dict[str, str],
    headers: dict[str, str],
    body: Any,
    matched_route_id: str | None,
    response_status: int,
) -> JournalEntry:
    return JournalEntry(
        method=request.method,
        path=request.url.path,
        query=query,
        headers=headers,
        body=body,
        matched_route_id=matched_route_id,
        response_status=response_status,
    )


if __name__ == "__main__":
    main()
