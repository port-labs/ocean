import json
from pathlib import Path
from typing import Any

import pytest

from tools.integration_validation.mock_server.exceptions import ResponseRenderError
from tools.integration_validation.mock_server.matcher import RouteMatch, match_route
from tools.integration_validation.mock_server.models import IncomingRequest, MockRoute
from tools.integration_validation.mock_server.responder import ResponseRenderer


def _match(
    route_id: str,
    response: dict[str, Any] | None = None,
    *,
    sequence: list[dict[str, Any]] | None = None,
    path_params: dict[str, str] | None = None,
) -> RouteMatch:
    route_data: dict[str, Any] = {
        "id": route_id,
        "request": {"method": "GET", "path": "/api/items"},
    }
    if sequence is not None:
        route_data["sequence"] = sequence
    else:
        route_data["response"] = response or {"status": 200}
    return RouteMatch(
        route=MockRoute.model_validate(route_data),
        path_params=path_params or {},
    )


class TestBodyFiles:
    def test_loads_parameterized_body_file(self, tmp_path: Path) -> None:
        bodies = tmp_path / "bodies"
        bodies.mkdir()
        (bodies / "team_team-1.json").write_text(
            json.dumps({"data": [{"id": "team-1"}]}),
            encoding="utf-8",
        )
        match = _match(
            "team",
            {
                "status": 200,
                "body_file": "bodies/team_{team_id}.json",
            },
            path_params={"team_id": "team-1"},
        )

        response = ResponseRenderer(tmp_path).render(match)

        assert response.body == {"data": [{"id": "team-1"}]}

    def test_uses_fallback_when_parameterized_file_is_missing(
        self, tmp_path: Path
    ) -> None:
        match = _match(
            "team-memberships",
            {
                "status": 200,
                "body_file": "bodies/memberships_{team_id}.json",
                "fallback_body": {"data": []},
            },
            path_params={"team_id": "unknown"},
        )

        response = ResponseRenderer(tmp_path).render(match)

        assert response.body == {"data": []}

    def test_missing_file_without_fallback_fails(self, tmp_path: Path) -> None:
        match = _match(
            "missing",
            {"status": 200, "body_file": "bodies/missing.json"},
        )

        with pytest.raises(
            ResponseRenderError,
            match="missing.*does not exist",
        ):
            ResponseRenderer(tmp_path).render(match)

    def test_invalid_json_file_fails(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{", encoding="utf-8")
        match = _match(
            "invalid-json",
            {"status": 200, "body_file": "bad.json"},
        )

        with pytest.raises(
            ResponseRenderError,
            match="invalid-json.*not valid JSON",
        ):
            ResponseRenderer(tmp_path).render(match)

    def test_body_file_cannot_escape_fixture_root(self, tmp_path: Path) -> None:
        match = _match(
            "unsafe",
            {"status": 200, "body_file": "../outside.json"},
        )

        with pytest.raises(ResponseRenderError, match="unsafe.*escapes fixture root"):
            ResponseRenderer(tmp_path).render(match)

    def test_body_file_requires_available_path_parameter(self, tmp_path: Path) -> None:
        match = _match(
            "missing-param",
            {"status": 200, "body_file": "bodies/{team_id}.json"},
        )

        with pytest.raises(
            ResponseRenderError,
            match="missing-param.*missing path parameter 'team_id'",
        ):
            ResponseRenderer(tmp_path).render(match)


class TestSequences:
    def test_returns_sequence_in_order_then_repeats_last_response(
        self, tmp_path: Path
    ) -> None:
        match = _match(
            "rate-limited",
            sequence=[
                {
                    "status": 429,
                    "headers": {"Retry-After": "1"},
                    "body": {"error": "rate limited"},
                },
                {"status": 200, "body": {"data": ["item"]}},
            ],
        )
        renderer = ResponseRenderer(tmp_path)

        first = renderer.render(match)
        second = renderer.render(match)
        third = renderer.render(match)

        assert first.status == 429
        assert first.headers == {"Retry-After": "1"}
        assert second.status == 200
        assert second.body == {"data": ["item"]}
        assert third == second

    def test_sequence_counters_are_per_route(self, tmp_path: Path) -> None:
        renderer = ResponseRenderer(tmp_path)
        first_route = _match(
            "first",
            sequence=[{"status": 429}, {"status": 200}],
        )
        second_route = _match(
            "second",
            sequence=[{"status": 500}, {"status": 204}],
        )

        assert renderer.render(first_route).status == 429
        assert renderer.render(second_route).status == 500
        assert renderer.render(first_route).status == 200

    def test_reset_restarts_sequences(self, tmp_path: Path) -> None:
        renderer = ResponseRenderer(tmp_path)
        match = _match(
            "rate-limited",
            sequence=[{"status": 429}, {"status": 200}],
        )

        renderer.render(match)
        renderer.render(match)
        renderer.reset()

        assert renderer.render(match).status == 429

    def test_sequence_does_not_advance_on_render_failure(self, tmp_path: Path) -> None:
        renderer = ResponseRenderer(tmp_path)
        match = _match(
            "paged",
            sequence=[
                {"status": 200, "body_file": "missing_page.json"},
                {"status": 200, "body": {"data": []}},
            ],
        )

        with pytest.raises(ResponseRenderError, match="paged.*does not exist"):
            renderer.render(match)

        (tmp_path / "missing_page.json").write_text(
            json.dumps({"data": ["item"]}),
            encoding="utf-8",
        )
        first_success = renderer.render(match)
        assert first_success.body == {"data": ["item"]}

        second_success = renderer.render(match)
        assert second_success.body == {"data": []}


class TestMatchingAndRendering:
    def test_datadog_style_pagination_stops_on_empty_page(self, tmp_path: Path) -> None:
        (tmp_path / "teams_page_0.json").write_text(
            json.dumps(
                {
                    "data": [{"id": "team-1"}],
                }
            ),
            encoding="utf-8",
        )
        routes = [
            MockRoute.model_validate(
                {
                    "id": "teams-page-0",
                    "request": {
                        "method": "GET",
                        "path": "/api/v2/team",
                        "query": {"page[number]": "0"},
                    },
                    "response": {
                        "status": 200,
                        "body_file": "teams_page_0.json",
                    },
                }
            ),
            MockRoute.model_validate(
                {
                    "id": "teams-page-1",
                    "request": {
                        "method": "GET",
                        "path": "/api/v2/team",
                        "query": {"page[number]": "1"},
                    },
                    "response": {"status": 200, "body": {"data": []}},
                }
            ),
        ]
        renderer = ResponseRenderer(tmp_path)

        first_match = match_route(
            routes,
            IncomingRequest(
                method="GET",
                path="/api/v2/team",
                query={"page[number]": "0", "page[size]": "100"},
            ),
        )
        second_match = match_route(
            routes,
            IncomingRequest(
                method="GET",
                path="/api/v2/team",
                query={"page[number]": "1", "page[size]": "100"},
            ),
        )

        assert first_match is not None
        assert second_match is not None
        first = renderer.render(first_match)
        second = renderer.render(second_match)

        assert first.body == {"data": [{"id": "team-1"}]}
        assert second.body == {"data": []}
