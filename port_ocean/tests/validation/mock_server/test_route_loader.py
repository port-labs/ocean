from pathlib import Path

import pytest

from port_ocean.validation.mock_server.exceptions import RouteFileLoadError
from port_ocean.validation.mock_server.loader import load_route_file, load_route_files


def _write_yaml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadRouteFile:
    def test_loads_valid_file(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "team.yaml",
            """
routes:
  - id: list-teams-page-0
    request:
      method: GET
      path: /api/v2/team
      query:
        page[number]: "0"
    response:
      status: 200
      body_file: bodies/teams_page_0.json
      response_model: team.TeamListResponse
  - id: team-memberships
    request:
      method: GET
      path: /api/v2/team/{team_id}/memberships
    response:
      status: 200
      body_file: bodies/team_memberships_{team_id}.json
      fallback_body: { "data": [], "included": [] }
      response_model: team.TeamMembershipsResponse
    verified: false
""",
        )

        route_file = load_route_file(path)

        assert [route.id for route in route_file.routes] == [
            "list-teams-page-0",
            "team-memberships",
        ]
        assert route_file.routes[1].verified is False
        assert route_file.routes[1].response is not None
        assert route_file.routes[1].response.fallback_body == {
            "data": [],
            "included": [],
        }

    def test_empty_file_yields_empty_routes(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path / "empty.yaml", "")
        assert load_route_file(path).routes == []

    def test_missing_file_includes_path_in_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.yaml"
        with pytest.raises(RouteFileLoadError, match=str(missing)) as exc_info:
            load_route_file(missing)
        assert "file not found" in str(exc_info.value)
        assert exc_info.value.path == missing

    def test_invalid_yaml_includes_path_in_error(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path / "bad.yaml", "routes:\n  - id: [\n")
        with pytest.raises(RouteFileLoadError, match=str(path)) as exc_info:
            load_route_file(path)
        assert "invalid YAML" in str(exc_info.value)

    def test_schema_error_includes_path_and_field(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "invalid.yaml",
            """
routes:
  - id: no-response
    request:
      method: GET
      path: /api/v2/team
""",
        )
        with pytest.raises(RouteFileLoadError, match=str(path)) as exc_info:
            load_route_file(path)
        message = str(exc_info.value)
        assert "exactly one of" in message
        assert message.startswith(f"Invalid mock route file '{path}':")

    def test_non_mapping_root_fails_clearly(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path / "list.yaml", "- just a list\n")
        with pytest.raises(RouteFileLoadError, match="expected a YAML mapping"):
            load_route_file(path)


class TestLoadRouteFilesOverrideById:
    def test_later_file_overrides_same_id(self, tmp_path: Path) -> None:
        base = _write_yaml(
            tmp_path / "base.yaml",
            """
routes:
  - id: list-teams
    request: { method: GET, path: /api/v2/team }
    response:
      status: 200
      body: { "data": ["base"] }
  - id: list-users
    request: { method: GET, path: /api/v2/users }
    response:
      status: 200
      body: { "data": [] }
""",
        )
        override = _write_yaml(
            tmp_path / "override.yaml",
            """
routes:
  - id: list-teams
    request: { method: GET, path: /api/v2/team }
    response:
      status: 200
      body: { "data": ["override"] }
    verified: false
""",
        )

        routes = load_route_files([base, override])

        assert [route.id for route in routes] == ["list-users", "list-teams"]
        teams = next(route for route in routes if route.id == "list-teams")
        assert teams.response is not None
        assert teams.response.body == {"data": ["override"]}
        assert teams.verified is False

    def test_preserves_order_when_no_override(self, tmp_path: Path) -> None:
        first = _write_yaml(
            tmp_path / "a.yaml",
            """
routes:
  - id: a
    request: { method: GET, path: /a }
    response: { status: 200, body: {} }
""",
        )
        second = _write_yaml(
            tmp_path / "b.yaml",
            """
routes:
  - id: b
    request: { method: GET, path: /b }
    response: { status: 200, body: {} }
""",
        )

        routes = load_route_files([first, second])
        assert [route.id for route in routes] == ["a", "b"]

    def test_stops_on_first_invalid_file(self, tmp_path: Path) -> None:
        good = _write_yaml(
            tmp_path / "good.yaml",
            """
routes:
  - id: ok
    request: { method: GET, path: /ok }
    response: { status: 200, body: {} }
""",
        )
        bad = _write_yaml(
            tmp_path / "bad.yaml",
            """
routes:
  - id: bad
    request: { method: GET, path: /bad }
""",
        )

        with pytest.raises(RouteFileLoadError, match=str(bad)):
            load_route_files([good, bad])
