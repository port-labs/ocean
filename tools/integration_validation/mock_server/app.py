"""FastAPI application factory for the integration-validation mock server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response

from tools.integration_validation.mock_server.admin import build_admin_router
from tools.integration_validation.mock_server.constants import MOCK_SERVER_METHODS
from tools.integration_validation.mock_server.request_handler import (
    dispatch_mock_request,
    parse_mock_request,
)
from tools.integration_validation.mock_server.responder import ResponseRenderer
from tools.integration_validation.mock_server.state import MockServerState


def create_mock_server_app(fixture_root: Path | str) -> FastAPI:
    """Create a mock-server app rooted at an integration's ``mock`` directory."""
    root = Path(fixture_root).resolve()
    state = MockServerState(
        fixture_root=root,
        renderer=ResponseRenderer(root),
    )
    app = FastAPI(title="Ocean Integration Validation Mock Server")
    app.include_router(build_admin_router(state))

    @app.api_route("/{request_path:path}", methods=MOCK_SERVER_METHODS)
    async def handle_mock_request(request: Request, request_path: str) -> Response:
        del request_path
        mock_request = await parse_mock_request(request)
        async with state.lock:
            return dispatch_mock_request(state, mock_request)

    return app
