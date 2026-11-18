"""Match incoming HTTP requests to configured mock routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tools.integration_validation.mock_server.models import MockRoute


@dataclass(frozen=True)
class RouteMatch:
    """The selected route and parameters captured from its path template."""

    route: MockRoute
    path_params: dict[str, str]


def match_route(
    routes: list[MockRoute],
    *,
    method: str,
    path: str,
    query: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    body: Any = None,
) -> RouteMatch | None:
    """Return the last route in ``routes`` matching an HTTP request.

    Query parameters, headers, and JSON objects use subset matching: only
    values declared by a route are required. List more specific routes after
    general ones so they take precedence.
    """
    request_query = query or {}
    request_headers = {key.lower(): value for key, value in (headers or {}).items()}

    for route in reversed(routes):
        expected = route.request
        if expected.method != method.upper():
            continue
        path_params = _match_path(expected.path, path)
        if path_params is None:
            continue
        if not _mapping_is_subset(expected.query, request_query):
            continue
        if not _mapping_is_subset(_lower_keys(expected.headers), request_headers):
            continue
        if expected.body is not None and not _json_is_subset(expected.body, body):
            continue
        return RouteMatch(route=route, path_params=path_params)

    return None


def _match_path(template: str, path: str) -> dict[str, str] | None:
    template_segments = template.split("/")
    path_segments = path.split("/")
    if len(template_segments) != len(path_segments):
        return None

    params: dict[str, str] = {}
    for expected, actual in zip(template_segments, path_segments):
        if expected.startswith("{") and expected.endswith("}"):
            if not actual:
                return None
            params[expected[1:-1]] = actual
        elif expected != actual:
            return None
    return params


def _lower_keys(mapping: Mapping[str, str] | None) -> dict[str, str] | None:
    if mapping is None:
        return None
    return {key.lower(): value for key, value in mapping.items()}


def _mapping_is_subset(
    expected: Mapping[str, str] | None, actual: Mapping[str, str]
) -> bool:
    if expected is None:
        return True
    return all(actual.get(key) == value for key, value in expected.items())


def _json_is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _json_is_subset(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        return all(
            _json_is_subset(expected_item, actual_item)
            for expected_item, actual_item in zip(expected, actual)
        )
    return expected == actual
