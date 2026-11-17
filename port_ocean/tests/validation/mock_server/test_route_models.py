import pytest
from pydantic import ValidationError

from port_ocean.validation.mock_server.models import (
    MockRoute,
    MockRouteFile,
    MockRouteRequest,
    MockRouteResponse,
)


class TestMockRouteRequest:
    def test_normalizes_method_case(self) -> None:
        request = MockRouteRequest.model_validate(
            {"method": "get", "path": "/api/v2/team"}
        )
        assert request.method == "GET"

    def test_stringifies_query_and_header_values(self) -> None:
        request = MockRouteRequest.model_validate(
            {
                "method": "GET",
                "path": "/api/v2/team",
                "query": {"page[number]": 0, "page[size]": None},
                "headers": {"X-RateLimit": 100},
            }
        )
        assert request.query == {"page[number]": "0", "page[size]": ""}
        assert request.headers == {"X-RateLimit": "100"}

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            MockRouteRequest.model_validate(
                {"method": "GET", "path": "/x", "unexpected": True}
            )


class TestMockRoute:
    def test_accepts_single_response(self) -> None:
        route = MockRoute.model_validate(
            {
                "id": "list-teams",
                "request": {"method": "GET", "path": "/api/v2/team"},
                "response": {
                    "status": 200,
                    "body_file": "bodies/teams.json",
                    "response_model": "team.TeamListResponse",
                },
                "verified": False,
            }
        )
        assert route.response is not None
        assert route.sequence is None
        assert route.verified is False

    def test_accepts_sequence(self) -> None:
        route = MockRoute.model_validate(
            {
                "id": "monitors-rate-limited",
                "request": {"method": "GET", "path": "/api/v1/monitor"},
                "sequence": [
                    {"status": 429, "headers": {"Retry-After": "1"}},
                    {"status": 200, "body_file": "bodies/monitors.json"},
                ],
            }
        )
        assert route.response is None
        assert route.sequence is not None
        assert len(route.sequence) == 2
        assert route.verified is True

    def test_rejects_both_response_and_sequence(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of"):
            MockRoute.model_validate(
                {
                    "id": "bad",
                    "request": {"method": "GET", "path": "/x"},
                    "response": {"status": 200, "body": {}},
                    "sequence": [{"status": 200, "body": {}}],
                }
            )

    def test_rejects_missing_response_and_sequence(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of"):
            MockRoute.model_validate(
                {
                    "id": "bad",
                    "request": {"method": "GET", "path": "/x"},
                }
            )

    def test_rejects_empty_sequence(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of"):
            MockRoute.model_validate(
                {
                    "id": "bad",
                    "request": {"method": "GET", "path": "/x"},
                    "sequence": [],
                }
            )


class TestMockRouteFile:
    def test_empty_routes_allowed(self) -> None:
        route_file = MockRouteFile.model_validate({})
        assert route_file.routes == []


class TestMockRouteResponse:
    def test_status_must_be_http_code(self) -> None:
        with pytest.raises(ValidationError):
            MockRouteResponse.model_validate({"status": 99})

    def test_strips_blank_optional_strings(self) -> None:
        response = MockRouteResponse.model_validate(
            {"status": 200, "body_file": "  ", "response_model": "  "}
        )
        assert response.body_file is None
        assert response.response_model is None
