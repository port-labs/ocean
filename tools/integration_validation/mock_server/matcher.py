"""Match incoming HTTP requests to configured mock routes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Pattern

from tools.integration_validation.mock_server.models import MockRoute, MockRouteRequest

_PATH_PARAMETER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


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
    """Return the most specific route matching an HTTP request.

    Query parameters, headers, and JSON objects use subset matching: only
    values declared by a route are required. When specificity is equal, the
    route appearing later in ``routes`` wins.
    """
    request_query = query or {}
    request_headers = {key.lower(): value for key, value in (headers or {}).items()}
    matches: list[tuple[tuple[int, int, int], int, MockRoute, dict[str, str]]] = []

    for index, route in enumerate(routes):
        path_params = _match_path(route.request.path, path)
        if path_params is None:
            continue
        if route.request.method != method.upper():
            continue
        if not _mapping_is_subset(route.request.query, request_query):
            continue

        expected_headers = (
            {key.lower(): value for key, value in route.request.headers.items()}
            if route.request.headers is not None
            else None
        )
        if not _mapping_is_subset(expected_headers, request_headers):
            continue
        if route.request.body is not None and not _json_is_subset(
            route.request.body, body
        ):
            continue

        matches.append((_specificity(route.request), index, route, path_params))

    if not matches:
        return None

    _, _, route, path_params = max(matches, key=lambda match: (match[0], match[1]))
    return RouteMatch(route=route, path_params=path_params)


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


def _match_path(template: str, path: str) -> dict[str, str] | None:
    pattern, parameter_names = _compile_path_template(template)
    match = pattern.fullmatch(path)
    if match is None:
        return None
    return dict(zip(parameter_names, match.groups()))


@lru_cache(maxsize=256)
def _compile_path_template(template: str) -> tuple[Pattern[str], tuple[str, ...]]:
    parameter_names: list[str] = []
    pattern_parts: list[str] = []
    position = 0

    for match in _PATH_PARAMETER_PATTERN.finditer(template):
        pattern_parts.append(re.escape(template[position : match.start()]))
        pattern_parts.append(r"([^/]+)")
        parameter_names.append(match.group(1))
        position = match.end()

    pattern_parts.append(re.escape(template[position:]))
    return re.compile("".join(pattern_parts)), tuple(parameter_names)


def _specificity(request: MockRouteRequest) -> tuple[int, int, int]:
    path_without_parameters = _PATH_PARAMETER_PATTERN.sub("", request.path)
    static_segments = sum(
        1
        for segment in request.path.strip("/").split("/")
        if segment and _PATH_PARAMETER_PATTERN.fullmatch(segment) is None
    )
    constraints = (
        len(request.query or {})
        + len(request.headers or {})
        + _json_constraint_count(request.body)
    )
    return static_segments, len(path_without_parameters), constraints


def _json_constraint_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, dict):
        return len(value) + sum(_json_constraint_count(item) for item in value.values())
    if isinstance(value, list):
        return 1 + sum(_json_constraint_count(item) for item in value)
    return 1
