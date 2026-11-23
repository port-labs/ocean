from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tools.integration_validation.mock_server.app import create_mock_server_app
from tools.integration_validation.mock_server.cli import run_mock_server
from tools.integration_validation.mock_server.constants import MOCK_SERVER_HOST


def _write_routes(validation_root: Path) -> Path:
    root = validation_root / "mock"
    routes = root / "routes"
    bodies = root / "bodies"
    models = validation_root / "models"
    routes.mkdir(parents=True)
    bodies.mkdir()
    models.mkdir()
    (models / "test.py").write_text(
        """
from typing import Any, ClassVar

from pydantic import BaseModel


class TestResponse(BaseModel):
    source: ClassVar[str] = "https://example.com/api"
    endpoint: ClassVar[str] = "test endpoint"

    data: Any = None
    id: str | None = None
""",
        encoding="utf-8",
    )
    (bodies / "team.json").write_text(
        '{"data": [{"id": "team-1"}]}',
        encoding="utf-8",
    )
    (routes / "team.yaml").write_text(
        """
routes:
  - id: list-teams
    request:
      method: GET
      path: /api/v2/team
      query:
        page: "0"
    response:
      status: 200
      headers:
        X-Mock-Route: list-teams
      body_file: bodies/team.json
      response_model: test.TestResponse

  - id: create-team
    request:
      method: POST
      path: /api/v2/team
      body:
        data:
          type: team
    response:
      status: 201
      body:
        id: created-team
      response_model: test.TestResponse

  - id: unused-route
    request:
      method: GET
      path: /api/v2/unused
    response:
      status: 200
      body: {}
      response_model: test.TestResponse

  - id: rate-limited
    request:
      method: GET
      path: /api/v1/monitor
    sequence:
      - status: 429
        headers:
          Retry-After: "1"
      - status: 200
        body:
          data: []
        response_model: test.TestResponse
""",
        encoding="utf-8",
    )
    return root


def _client(root: Path) -> TestClient:
    mock_root = _write_routes(root)
    return TestClient(create_mock_server_app(mock_root))


def _load_scenario(client: TestClient) -> None:
    response = client.post(
        "/__admin/scenario",
        json={"routes": ["routes/team.yaml"]},
    )
    assert response.status_code == 200


class TestScenarioAdmin:
    def test_loads_route_files(self, tmp_path: Path) -> None:
        client = _client(tmp_path)

        response = client.post(
            "/__admin/scenario",
            json={"routes": ["routes/team.yaml"]},
        )

        assert response.status_code == 200
        assert response.json() == {
            "route_ids": [
                "list-teams",
                "create-team",
                "unused-route",
                "rate-limited",
            ]
        }

    def test_invalid_route_file_returns_422(self, tmp_path: Path) -> None:
        client = _client(tmp_path)

        response = client.post(
            "/__admin/scenario",
            json={"routes": ["routes/missing.yaml"]},
        )

        assert response.status_code == 422
        assert "missing.yaml" in response.json()["detail"]

    def test_route_file_cannot_escape_fixture_root(self, tmp_path: Path) -> None:
        client = _client(tmp_path)

        response = client.post(
            "/__admin/scenario",
            json={"routes": ["../outside.yaml"]},
        )

        assert response.status_code == 422
        assert "escapes fixture root" in response.json()["detail"]


class TestMockRequests:
    def test_serves_matched_route_and_records_it(self, tmp_path: Path) -> None:
        client = _client(tmp_path)
        _load_scenario(client)

        response = client.get(
            "/api/v2/team",
            params={"page": "0", "page_size": "100"},
        )

        assert response.status_code == 200
        assert response.headers["X-Mock-Route"] == "list-teams"
        assert response.json() == {"data": [{"id": "team-1"}]}

        journal = client.get("/__admin/journal").json()
        assert journal["route_call_counts"] == {
            "list-teams": 1,
            "create-team": 0,
            "unused-route": 0,
            "rate-limited": 0,
        }
        assert len(journal["requests"]) == 1
        entry = journal["requests"][0]
        assert entry["method"] == "GET"
        assert entry["path"] == "/api/v2/team"
        assert entry["query"] == {"page": "0", "page_size": "100"}
        assert entry["body"] is None
        assert entry["matched_route_id"] == "list-teams"
        assert entry["response_status"] == 200

    def test_matches_json_body_subset(self, tmp_path: Path) -> None:
        client = _client(tmp_path)
        _load_scenario(client)

        response = client.post(
            "/api/v2/team",
            json={
                "data": {
                    "type": "team",
                    "attributes": {"name": "Platform"},
                }
            },
        )

        assert response.status_code == 201
        assert response.json() == {"id": "created-team"}

    def test_unmatched_request_returns_599_and_is_recorded(
        self, tmp_path: Path
    ) -> None:
        client = _client(tmp_path)
        _load_scenario(client)

        response = client.get("/api/v2/users")

        assert response.status_code == 599
        assert response.json()["error"] == "unmatched_request"
        assert "GET /api/v2/users" in response.json()["message"]

        unmatched = client.get("/__admin/unmatched").json()
        assert len(unmatched) == 1
        assert unmatched[0]["path"] == "/api/v2/users"
        assert unmatched[0]["matched_route_id"] is None
        assert unmatched[0]["response_status"] == 599

    def test_unused_lists_only_routes_not_called(self, tmp_path: Path) -> None:
        client = _client(tmp_path)
        _load_scenario(client)

        client.get("/api/v2/team", params={"page": "0"})

        assert client.get("/__admin/unused").json() == [
            {"route_id": "create-team", "call_count": 0},
            {"route_id": "unused-route", "call_count": 0},
            {"route_id": "rate-limited", "call_count": 0},
        ]


class TestReset:
    def test_reset_clears_journal_counts_and_sequence_state(
        self, tmp_path: Path
    ) -> None:
        client = _client(tmp_path)
        _load_scenario(client)
        assert client.get("/api/v1/monitor").status_code == 429
        assert client.get("/api/v1/monitor").status_code == 200

        response = client.post("/__admin/reset")

        assert response.status_code == 200
        assert response.json() == {"status": "reset"}
        assert client.get("/__admin/journal").json() == {
            "requests": [],
            "route_call_counts": {
                "list-teams": 0,
                "create-team": 0,
                "unused-route": 0,
                "rate-limited": 0,
            },
        }
        assert client.get("/api/v1/monitor").status_code == 429


def test_run_mock_server_binds_to_loopback(tmp_path: Path, monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(app: Any, *, host: str, port: int) -> None:
        captured.update(app=app, host=host, port=port)

    monkeypatch.setattr(
        "tools.integration_validation.mock_server.cli.uvicorn.run",
        fake_run,
    )

    run_mock_server(tmp_path, 9123)

    assert captured["host"] == MOCK_SERVER_HOST == "127.0.0.1"
    assert captured["port"] == 9123
