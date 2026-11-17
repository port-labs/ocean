from typing import Any

import pytest

from tools.integration_validation.mock_server.matcher import match_route
from tools.integration_validation.mock_server.models import MockRoute


def _route(
    route_id: str,
    *,
    method: str = "GET",
    path: str = "/api/items",
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    body: Any = None,
) -> MockRoute:
    request: dict[str, Any] = {"method": method, "path": path}
    if query is not None:
        request["query"] = query
    if headers is not None:
        request["headers"] = headers
    if body is not None:
        request["body"] = body
    return MockRoute.model_validate(
        {
            "id": route_id,
            "request": request,
            "response": {"status": 200, "body": {}},
        }
    )


class TestMethodAndPathMatching:
    def test_matches_method_case_insensitively(self) -> None:
        route = _route("items")

        match = match_route([route], method="get", path="/api/items")

        assert match is not None
        assert match.route.id == "items"

    @pytest.mark.parametrize(
        ("method", "path"),
        [("POST", "/api/items"), ("GET", "/api/other")],
    )
    def test_rejects_method_or_path_mismatch(self, method: str, path: str) -> None:
        assert match_route([_route("items")], method=method, path=path) is None

    def test_captures_path_template_parameters(self) -> None:
        route = _route(
            "team-memberships",
            path="/api/v2/team/{team_id}/memberships/{membership_id}",
        )

        match = match_route(
            [route],
            method="GET",
            path="/api/v2/team/team-1/memberships/member-2",
        )

        assert match is not None
        assert match.path_params == {
            "team_id": "team-1",
            "membership_id": "member-2",
        }

    def test_path_parameter_does_not_cross_slashes(self) -> None:
        route = _route("team", path="/api/teams/{team_id}")

        assert (
            match_route(
                [route],
                method="GET",
                path="/api/teams/platform/members",
            )
            is None
        )


class TestSubsetMatching:
    def test_query_is_a_subset(self) -> None:
        route = _route("first-page", query={"page[number]": "0"})

        match = match_route(
            [route],
            method="GET",
            path="/api/items",
            query={"page[number]": "0", "page[size]": "100"},
        )

        assert match is not None
        assert match.route.id == "first-page"

    def test_rejects_query_value_mismatch(self) -> None:
        route = _route("first-page", query={"page[number]": "0"})

        assert (
            match_route(
                [route],
                method="GET",
                path="/api/items",
                query={"page[number]": "1"},
            )
            is None
        )

    def test_headers_are_case_insensitive_subsets(self) -> None:
        route = _route("json", headers={"Content-Type": "application/json"})

        match = match_route(
            [route],
            method="GET",
            path="/api/items",
            headers={
                "content-type": "application/json",
                "authorization": "Bearer fake",
            },
        )

        assert match is not None

    def test_body_is_a_recursive_json_subset(self) -> None:
        route = _route(
            "active-team",
            method="POST",
            body={
                "data": {
                    "type": "team",
                    "attributes": {"active": True},
                }
            },
        )

        match = match_route(
            [route],
            method="POST",
            path="/api/items",
            body={
                "data": {
                    "id": "team-1",
                    "type": "team",
                    "attributes": {"active": True, "name": "Platform"},
                },
                "meta": {"source": "test"},
            },
        )

        assert match is not None

    def test_rejects_nested_body_mismatch(self) -> None:
        route = _route(
            "active-team",
            method="POST",
            body={"data": {"attributes": {"active": True}}},
        )

        assert (
            match_route(
                [route],
                method="POST",
                path="/api/items",
                body={"data": {"attributes": {"active": False}}},
            )
            is None
        )

    def test_lists_require_same_length_but_objects_inside_use_subsets(self) -> None:
        route = _route(
            "tagged",
            method="POST",
            body={"items": [{"id": "one"}]},
        )

        match = match_route(
            [route],
            method="POST",
            path="/api/items",
            body={"items": [{"id": "one", "name": "First"}]},
        )

        assert match is not None
        assert (
            match_route(
                [route],
                method="POST",
                path="/api/items",
                body={"items": [{"id": "one"}, {"id": "two"}]},
            )
            is None
        )


class TestPrecedence:
    def test_exact_path_beats_path_template(self) -> None:
        routes = [
            _route("template", path="/api/items/{item_id}"),
            _route("exact", path="/api/items/special"),
        ]

        match = match_route(routes, method="GET", path="/api/items/special")

        assert match is not None
        assert match.route.id == "exact"

    def test_more_subset_constraints_win_for_same_path(self) -> None:
        routes = [
            _route("generic"),
            _route("first-page", query={"page": "1"}),
            _route(
                "first-json-page",
                query={"page": "1"},
                headers={"Accept": "application/json"},
            ),
        ]

        match = match_route(
            routes,
            method="GET",
            path="/api/items",
            query={"page": "1"},
            headers={"accept": "application/json"},
        )

        assert match is not None
        assert match.route.id == "first-json-page"

    def test_body_constraint_beats_unconstrained_route(self) -> None:
        routes = [
            _route("generic", method="POST"),
            _route("empty-items", method="POST", body={"items": []}),
        ]

        match = match_route(
            routes,
            method="POST",
            path="/api/items",
            body={"items": []},
        )

        assert match is not None
        assert match.route.id == "empty-items"

    def test_later_route_wins_when_specificity_is_equal(self) -> None:
        routes = [_route("first"), _route("second")]

        match = match_route(routes, method="GET", path="/api/items")

        assert match is not None
        assert match.route.id == "second"
