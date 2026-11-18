"""Catch-all mock request dispatch and request helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from tools.integration_validation.mock_server.constants import UNMATCHED_RESPONSE_STATUS
from tools.integration_validation.mock_server.exceptions import ResponseRenderError
from tools.integration_validation.mock_server.matcher import match_route
from tools.integration_validation.mock_server.responder import RenderedResponse
from tools.integration_validation.mock_server.schemas import JournalEntry
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


def journal_entry(
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


def _unmatched_json_response(
    request: Request,
    query: dict[str, str],
) -> JSONResponse:
    return JSONResponse(
        status_code=UNMATCHED_RESPONSE_STATUS,
        content={
            "error": "unmatched_request",
            "message": (
                f"No mock route matched " f"{request.method} {request.url.path}"
            ),
            "request": {
                "method": request.method,
                "path": request.url.path,
                "query": query,
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


def dispatch_mock_request(
    state: MockServerState,
    request: Request,
    *,
    query: dict[str, str],
    headers: dict[str, str],
    body: Any,
) -> Response:
    """Match, journal, and render. Caller must hold ``state.lock``."""
    route_match = match_route(
        state.routes,
        method=request.method,
        path=request.url.path,
        query=query,
        headers=headers,
        body=body,
    )
    if route_match is None:
        state.journal.append(
            journal_entry(
                request=request,
                query=query,
                headers=headers,
                body=body,
                matched_route_id=None,
                response_status=UNMATCHED_RESPONSE_STATUS,
            )
        )
        return _unmatched_json_response(request, query)

    route_id = route_match.route.id
    state.route_call_counts[route_id] = state.route_call_counts.get(route_id, 0) + 1
    try:
        rendered = state.renderer.render(route_match)
    except ResponseRenderError as exc:
        state.journal.append(
            journal_entry(
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
        journal_entry(
            request=request,
            query=query,
            headers=headers,
            body=body,
            matched_route_id=route_id,
            response_status=rendered.status,
        )
    )
    return _as_http_response(rendered)
