"""Catch-all mock request dispatch and request helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from tools.integration_validation.mock_server.constants import UNMATCHED_RESPONSE_STATUS
from tools.integration_validation.mock_server.exceptions import ResponseRenderError
from tools.integration_validation.mock_server.matcher import RouteMatch, match_route
from tools.integration_validation.mock_server.models import IncomingRequest
from tools.integration_validation.mock_server.responder import RenderedResponse
from tools.integration_validation.mock_server.admin_schemas import JournalEntry
from tools.integration_validation.mock_server.state import MockServerState


def resolve_fixture_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Route file '{relative_path}' escapes fixture root '{root}'"
        ) from exc
    return path


async def read_request_body(request: Request) -> Any:
    raw_body = await request.body()
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw_body.decode("utf-8", errors="replace")


async def parse_mock_request(request: Request) -> IncomingRequest:
    return IncomingRequest(
        method=request.method,
        path=request.url.path,
        query=dict(request.query_params),
        headers=dict(request.headers),
        body=await read_request_body(request),
    )


def _unmatched_json_response(request: IncomingRequest) -> JSONResponse:
    return JSONResponse(
        status_code=UNMATCHED_RESPONSE_STATUS,
        content={
            "error": "unmatched_request",
            "message": f"No mock route matched {request.method} {request.path}",
            "request": {
                "method": request.method,
                "path": request.path,
                "query": request.query,
            },
        },
    )


def _as_http_response(rendered: RenderedResponse) -> Response:
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


def _respond(
    state: MockServerState,
    request: IncomingRequest,
    route_match: RouteMatch | None,
) -> Response:
    if route_match is None:
        return _unmatched_json_response(request)

    route_id = route_match.route.id
    state.route_call_counts[route_id] = state.route_call_counts.get(route_id, 0) + 1
    try:
        rendered = state.renderer.render(route_match)
    except ResponseRenderError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": "response_render_error",
                "message": str(exc),
                "route_id": route_id,
            },
        )
    return _as_http_response(rendered)


def dispatch_mock_request(state: MockServerState, request: IncomingRequest) -> Response:
    """Match, journal, and render. Caller must hold ``state.lock``."""
    route_match = match_route(state.routes, request)
    response = _respond(state, request, route_match)
    state.journal.append(
        JournalEntry(
            **asdict(request),
            matched_route_id=route_match.route.id if route_match else None,
            response_status=response.status_code,
        )
    )
    return response
