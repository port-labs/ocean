"""Tests for the integration validation runner CLI."""

import json
from pathlib import Path

import pytest

from tools.integration_validation.mock_server.admin_schemas import JournalEntry
from tools.integration_validation.runner.results import collect as collect_module
from tools.integration_validation.runner import runner as runner_module
from tools.integration_validation.runner.integration.process import IntegrationRunResult
from tools.integration_validation.runner.main import main
from tools.integration_validation.runner.results.mock_journal import MockJournal
from tools.integration_validation.tests.runner.test_port_client import FakePortClient

MOCK_BASE_URL = "http://127.0.0.1:9000"


@pytest.fixture(autouse=True)
def fake_ocean_sail(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_sail(*_args: object, **_kwargs: object) -> IntegrationRunResult:
        return IntegrationRunResult(
            returncode=0,
            stdout="",
            stderr="",
            timed_out=False,
        )

    monkeypatch.setattr(runner_module, "run_ocean_sail_once", fake_sail)


@pytest.fixture(autouse=True)
def fake_mock_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(mock_base_url: str) -> MockJournal:
        return MockJournal(requests=[], route_call_counts={})

    monkeypatch.setattr(collect_module, "fetch_mock_journal", fake_fetch)


def _cli_args(integration_root: Path, *extra: str) -> list[str]:
    return [str(integration_root), "--mock-base-url", MOCK_BASE_URL, *extra]


@pytest.fixture
def fake_port_clients(monkeypatch: pytest.MonkeyPatch) -> dict[str, FakePortClient]:
    clients: dict[str, FakePortClient] = {}

    def factory(integration_identifier: str, integration_type: str) -> FakePortClient:
        assert integration_type == "sample"
        clients[integration_identifier] = FakePortClient()
        return clients[integration_identifier]

    monkeypatch.setattr(runner_module, "create_port_client", factory)
    return clients


@pytest.fixture
def validation_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_port_clients: dict[str, FakePortClient],
) -> Path:
    integration_root = tmp_path / "sample"
    validation_root = integration_root / "validation"
    routes_root = validation_root / "mock" / "routes"
    routes_root.mkdir(parents=True)
    (routes_root / "team.yaml").write_text(
        """
routes:
  - id: list-teams
    request: {method: GET, path: /teams}
    response: {status: 200, body: []}
  - id: get-team
    request: {method: GET, path: "/teams/{id}"}
    response: {status: 200, body: {}}
    verified: false
""",
        encoding="utf-8",
    )
    (integration_root / ".port" / "resources").mkdir(parents=True)
    (integration_root / ".port" / "spec.json").write_text(
        json.dumps({"type": "sample"}), encoding="utf-8"
    )
    (integration_root / ".port" / "resources" / "port-app-config.yaml").write_text(
        """
resources:
  - kind: team
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          blueprint: '"sampleTeam"'
""",
        encoding="utf-8",
    )
    (integration_root / ".port" / "resources" / "blueprints.json").write_text(
        json.dumps([{"identifier": "sampleTeam", "title": "Team", "schema": {}}]),
        encoding="utf-8",
    )
    (validation_root / "scenarios.yaml").write_text(
        """
defaults:
  integration_config:
    exampleBaseUrl: "{{mock_base_url}}"
  port_app_config: .port/resources/port-app-config.yaml
scenarios:
  happy_path:
    kinds: [team]
    routes: [routes/team.yaml]
""",
        encoding="utf-8",
    )
    (integration_root / ".env").write_text(
        "\n".join(
            [
                "OCEAN__INTEGRATION__TYPE=sample",
                "OCEAN__PORT__CLIENT_ID=test-client",
                "OCEAN__PORT__CLIENT_SECRET=test-secret",
                "OCEAN__PORT__BASE_URL=https://api.getport.io",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(integration_root)
    return integration_root


def test_validate_help_lists_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--scenario" in output
    assert "--update-expected" in output
    assert "--skip-cleanup" in output
    assert "--report" in output
    assert "--mock-base-url" in output
    assert "--integration-timeout" in output


def test_validate_malformed_scenarios_yaml_exits_2(tmp_path: Path) -> None:
    integration_root = tmp_path / "broken"
    validation_root = integration_root / "validation"
    validation_root.mkdir(parents=True)
    (validation_root / "scenarios.yaml").write_text(
        """
defaults:
  port_app_config: missing.yaml
scenarios:
  happy_path:
    routes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(integration_root))

    assert exc_info.value.code == 2


def test_validate_malformed_scenarios_yaml_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    integration_root = tmp_path / "broken"
    validation_root = integration_root / "validation"
    validation_root.mkdir(parents=True)
    (validation_root / "scenarios.yaml").write_text(
        """
defaults:
  port_app_config: missing.yaml
scenarios:
  happy_path:
    routes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(_cli_args(integration_root))

    err = capsys.readouterr().err
    assert "Setup error" in err
    assert "scenarios.yaml" in err


def test_validate_prepares_and_cleans_up_port_for_each_scenario(
    validation_integration: Path,
    fake_port_clients: dict[str, FakePortClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(_cli_args(validation_integration))

    out = capsys.readouterr()
    assert "happy_path" in out.out
    assert "PASS  happy_path" in out.out
    assert "kept in Port" not in out.err
    (identifier, client), *_ = fake_port_clients.items()
    assert identifier == "validate-sample-happy-path"
    created = next(
        payload for name, payload in client.calls if name == "create_blueprint"
    )
    assert created["identifier"] == "sampleTeam-happy-path"
    integration_config = next(
        payload for name, payload in client.calls if name == "create_integration"
    )
    blueprint = integration_config["resources"][0]["port"]["entity"]["mappings"][
        "blueprint"
    ]
    assert blueprint == json.dumps(created["identifier"])
    assert client.names()[-2:] == ["delete_integration", "delete_blueprint"]


def test_validate_skip_cleanup_keeps_port_resources_and_reports_them(
    validation_integration: Path,
    fake_port_clients: dict[str, FakePortClient],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report_path = tmp_path / "report.json"

    main(
        _cli_args(
            validation_integration, "--skip-cleanup", "--report", str(report_path)
        )
    )

    assert "kept in Port: validate-sample-happy-path" in capsys.readouterr().err
    (client,) = fake_port_clients.values()
    names = client.names()
    assert "delete_integration" not in names[names.index("mark_initialized") :]
    assert client.blueprints == {"sampleTeam-happy-path"}
    report = json.loads(report_path.read_text())
    port = report["scenarios"][0]["port"]
    assert port["cleaned_up"] is False
    assert list(port["blueprints"]) == ["sampleTeam"]


def test_validate_rejects_mapping_to_unknown_blueprint_before_touching_port(
    validation_integration: Path,
    fake_port_clients: dict[str, FakePortClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    (validation_integration / ".port" / "resources" / "blueprints.json").write_text(
        json.dumps([{"identifier": "otherBlueprint"}]), encoding="utf-8"
    )

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(validation_integration))

    assert exc_info.value.code == 2
    assert "sampleTeam" in capsys.readouterr().err
    assert fake_port_clients == {}


def test_validate_cleans_up_when_integration_step_raises(
    validation_integration: Path,
    fake_port_clients: dict[str, FakePortClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sail blew up")

    monkeypatch.setattr(runner_module, "run_ocean_sail_once", boom)

    with pytest.raises(RuntimeError, match="sail blew up"):
        runner_module.run_validate(
            runner_module.ValidateOptions(
                integration_path=validation_integration,
                scenario_names=None,
                update_expected=False,
                skip_cleanup=False,
                report_path=None,
                mock_base_url=MOCK_BASE_URL,
                integration_timeout_seconds=30,
            )
        )

    (client,) = fake_port_clients.values()
    assert "delete_integration" in client.names()
    assert "delete_blueprint" in client.names()


def test_validate_with_mock_base_url_runs_sail_after_port_prep(
    validation_integration: Path,
    fake_port_clients: dict[str, FakePortClient],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sail_calls: list[str] = []

    def fake_sail(
        integration_root: Path,
        *,
        integration_identifier: str,
        **kwargs: object,
    ) -> IntegrationRunResult:
        sail_calls.append(integration_identifier)
        return IntegrationRunResult(
            returncode=0,
            stdout="",
            stderr="",
            timed_out=False,
        )

    monkeypatch.setattr(runner_module, "run_ocean_sail_once", fake_sail)

    main(_cli_args(validation_integration))

    assert sail_calls == ["validate-sample-happy-path"]
    assert "1 passed, 0 failed" in capsys.readouterr().out


def test_validate_collects_entities_before_cleanup_and_reports_them(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clients: list[FakePortClient] = []

    def factory(integration_identifier: str, integration_type: str) -> FakePortClient:
        client = FakePortClient(
            entities={"sampleTeam-happy-path": [{"identifier": "platform"}]}
        )
        clients.append(client)
        return client

    monkeypatch.setattr(runner_module, "create_port_client", factory)
    report_path = tmp_path / "report.json"

    main(_cli_args(validation_integration, "--report", str(report_path)))

    (client,) = clients
    names = client.names()
    assert names.index("search_entities") < names.index(
        "delete_integration", names.index("mark_initialized")
    )
    assert "1 entities" in capsys.readouterr().out
    collection = json.loads(report_path.read_text())["scenarios"][0]["collection"]
    assert collection["resync_status"] == "completed"
    assert collection["entity_counts"] == {"sampleTeam": 1}


@pytest.fixture
def team_entities(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Entities the fake Port returns for the run's team blueprint; edit to change them."""
    entities: list[dict[str, object]] = [
        {
            "identifier": "platform",
            "blueprint": "sampleTeam-happy-path",
            "properties": {"handle": "platform"},
        }
    ]

    def factory(integration_identifier: str, integration_type: str) -> FakePortClient:
        return FakePortClient(entities={"sampleTeam-happy-path": entities})

    monkeypatch.setattr(runner_module, "create_port_client", factory)
    return entities


def test_validate_first_run_writes_expected_and_passes(
    validation_integration: Path,
    team_entities: list[dict[str, object]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report_path = tmp_path / "report.json"

    main(_cli_args(validation_integration, "--report", str(report_path)))

    snapshot = validation_integration / "validation/expected/happy_path/sampleTeam.json"
    assert json.loads(snapshot.read_text()) == [
        {"identifier": "platform", "properties": {"handle": "platform"}}
    ]
    assert "expected entities matched" in capsys.readouterr().out
    report = json.loads(report_path.read_text())
    assert report["status"] == "passed"
    assert report["scenarios"][0]["comparison"]["status"] == "matched"


def test_validate_entity_diff_fails_and_reports_the_field(
    validation_integration: Path,
    team_entities: list[dict[str, object]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(_cli_args(validation_integration))
    team_entities[0]["properties"] = {"handle": None}
    report_path = tmp_path / "report.json"

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(validation_integration, "--report", str(report_path)))

    assert exc_info.value.code == 1
    out, err = capsys.readouterr()
    assert "FAIL  happy_path" in out
    assert "expected entities 1 difference(s) from" in out
    assert 'sampleTeam platform properties.handle: "platform" -> null' in err
    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert report["scenarios"][0]["comparison"]["entity_diff"] == {
        "sampleTeam": {
            "added": [],
            "removed": [],
            "changed": [
                {
                    "identifier": "platform",
                    "field": "properties.handle",
                    "expected": "platform",
                    "actual": None,
                }
            ],
        }
    }


def test_validate_update_expected_accepts_the_new_result(
    validation_integration: Path,
    team_entities: list[dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(_cli_args(validation_integration))
    team_entities.append({"identifier": "infra", "blueprint": "sampleTeam-happy-path"})

    main(_cli_args(validation_integration, "--update-expected"))
    main(_cli_args(validation_integration))

    snapshot = validation_integration / "validation/expected/happy_path/sampleTeam.json"
    assert [entity["identifier"] for entity in json.loads(snapshot.read_text())] == [
        "infra",
        "platform",
    ]
    assert "difference(s)" not in capsys.readouterr().out


def test_validate_missing_port_credentials_exits_2(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key in (
        "OCEAN__PORT__CLIENT_ID",
        "OCEAN__PORT__CLIENT_SECRET",
        "OCEAN__PORT__BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    (validation_integration / ".env").unlink()

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(validation_integration))

    assert exc_info.value.code == 2
    assert "Missing Port credentials" in capsys.readouterr().err


def test_validate_missing_integration_type_exits_2(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OCEAN__INTEGRATION__TYPE", raising=False)
    (validation_integration / ".env").write_text(
        "\n".join(
            [
                "OCEAN__PORT__CLIENT_ID=test-client",
                "OCEAN__PORT__CLIENT_SECRET=test-secret",
                "OCEAN__PORT__BASE_URL=https://api.getport.io",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(validation_integration))

    assert exc_info.value.code == 2
    assert "OCEAN__INTEGRATION__TYPE" in capsys.readouterr().err


def test_validate_report_has_verdict_totals_and_unverified_routes(
    validation_integration: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report_path = tmp_path / "report.json"

    main(_cli_args(validation_integration, "--report", str(report_path)))

    assert "Unverified routes: get-team" in capsys.readouterr().out
    report = json.loads(report_path.read_text())
    assert report["totals"] == {"passed": 1, "failed": 0}
    (scenario,) = report["scenarios"]
    assert scenario["passed"] is True
    assert scenario["unverified_routes"] == ["get-team"]


def _unmatched_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(mock_base_url: str) -> MockJournal:
        return MockJournal(
            requests=[
                JournalEntry(
                    method="GET",
                    path="/teams/platform/members",
                    query={},
                    headers={},
                    matched_route_id=None,
                    response_status=599,
                )
            ],
            route_call_counts={},
        )

    monkeypatch.setattr(collect_module, "fetch_mock_journal", fake_fetch)


def test_validate_unmatched_request_fails_the_scenario(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _unmatched_journal(monkeypatch)
    report_path = tmp_path / "report.json"

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(validation_integration, "--report", str(report_path)))

    assert exc_info.value.code == 1
    assert "unmatched: GET /teams/platform/members" in capsys.readouterr().err
    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert report["scenarios"][0]["passed"] is False


def test_validate_scenario_can_allow_unmatched_requests(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _unmatched_journal(monkeypatch)
    scenarios_file = validation_integration / "validation" / "scenarios.yaml"
    scenarios_file.write_text(
        scenarios_file.read_text() + "    expect:\n      unmatched_requests: allow\n",
        encoding="utf-8",
    )

    main(_cli_args(validation_integration))

    assert "PASS  happy_path" in capsys.readouterr().out


def test_validate_setup_error_still_writes_a_report(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "OCEAN__PORT__CLIENT_ID",
        "OCEAN__PORT__CLIENT_SECRET",
        "OCEAN__PORT__BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    (validation_integration / ".env").unlink()
    report_path = tmp_path / "report.json"

    with pytest.raises(SystemExit) as exc_info:
        main(_cli_args(validation_integration, "--report", str(report_path)))

    assert exc_info.value.code == 2
    report = json.loads(report_path.read_text())
    assert report["status"] == "error"
    assert report["error"].startswith("Setup error: Missing Port credentials")
    assert report["scenarios"] == []
