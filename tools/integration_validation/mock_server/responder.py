"""Resolve matched mock routes into concrete HTTP responses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from tools.integration_validation.mock_server.exceptions import ResponseRenderError
from tools.integration_validation.mock_server.matcher import RouteMatch
from tools.integration_validation.mock_server.models import MockRoute, MockRouteResponse

_BODY_FILE_PATH_PARAMETER_PATTERN = re.compile(
    r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})"
)


@dataclass(frozen=True)
class RenderedResponse:
    """A fully resolved response ready for the HTTP layer."""

    status: int
    headers: dict[str, str]
    body: Any


class ResponseRenderer:
    """Render route responses while tracking per-route sequence state."""

    def __init__(self, fixture_root: Path | str) -> None:
        self._fixture_root = Path(fixture_root).resolve()
        self._sequence_calls: dict[str, int] = {}

    def render(self, match: RouteMatch) -> RenderedResponse:
        """Render the next response for a matched route."""
        response = self._response_for_current_sequence_step(match.route)
        body = self._load_body(match.route.id, response, match.path_params)
        self._advance_sequence_step(match.route)

        return RenderedResponse(
            status=response.status,
            headers=dict(response.headers or {}),
            body=body,
        )

    def reset(self) -> None:
        """Reset all sequence counters, such as when loading a new scenario."""
        self._sequence_calls.clear()

    def _response_for_current_sequence_step(
        self, route: MockRoute
    ) -> MockRouteResponse:
        if route.sequence is None:
            if route.response is None:
                raise ResponseRenderError(route.id, "route has no response")
            return route.response

        call_index = self._sequence_calls.get(route.id, 0)
        return route.sequence[min(call_index, len(route.sequence) - 1)]

    def _advance_sequence_step(self, route: MockRoute) -> None:
        if route.sequence is None:
            return

        call_index = self._sequence_calls.get(route.id, 0)
        self._sequence_calls[route.id] = call_index + 1

    def _load_body(
        self,
        route_id: str,
        response: MockRouteResponse,
        path_params: Mapping[str, str],
    ) -> Any:
        if response.body_file is None:
            return response.body

        relative_path = _render_body_file_path(
            response.body_file, path_params, route_id
        )
        body_path = (self._fixture_root / relative_path).resolve()
        try:
            body_path.relative_to(self._fixture_root)
        except ValueError as exc:
            raise ResponseRenderError(
                route_id,
                f"body_file '{relative_path}' escapes fixture root",
            ) from exc

        if not body_path.exists():
            if response.fallback_body is not None:
                return response.fallback_body
            raise ResponseRenderError(
                route_id,
                f"body_file '{relative_path}' does not exist",
            )
        if not body_path.is_file():
            raise ResponseRenderError(
                route_id,
                f"body_file '{relative_path}' is not a file",
            )

        try:
            return json.loads(body_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ResponseRenderError(
                route_id,
                f"could not read body_file '{relative_path}': {exc}",
            ) from exc
        except json.JSONDecodeError as exc:
            raise ResponseRenderError(
                route_id,
                f"body_file '{relative_path}' is not valid JSON: {exc}",
            ) from exc


def _render_body_file_path(
    template: str,
    path_params: Mapping[str, str],
    route_id: str,
) -> str:
    def replace(match: re.Match[str]) -> str:
        parameter = match.group(1)
        if parameter not in path_params:
            raise ResponseRenderError(
                route_id,
                f"body_file references missing path parameter '{parameter}'",
            )
        return path_params[parameter]

    return _BODY_FILE_PATH_PARAMETER_PATTERN.sub(replace, template)
