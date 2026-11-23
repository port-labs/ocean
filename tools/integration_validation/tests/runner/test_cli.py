"""Tests for the integration validation runner CLI."""

import json
from pathlib import Path

import pytest

from tools.integration_validation.runner import runner as runner_module
from tools.integration_validation.runner.main import main
from tools.integration_validation.tests.runner.test_port_setup import FakePortClient


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
    mock_root = validation_root / "mock"
    mock_root.mkdir(parents=True)
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
                "OCEAN__PORT__CLIENT_ID=test-client",
                "OCEAN__PORT__CLIENT_SECRET=test-secret",
                "OCEAN__PORT__BASE_URL=https://api.getport.io",
                "OCEAN__INTEGRATION__TYPE=sample",
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
        main([str(integration_root)])

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
        main([str(integration_root)])

    err = capsys.readouterr().err
    assert "Setup error" in err
    assert "scenarios.yaml" in err


def test_validate_prepares_and_cleans_up_port_for_each_scenario(
    validation_integration: Path,
    fake_port_clients: dict[str, FakePortClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(validation_integration)])

    out = capsys.readouterr()
    assert "happy_path" in out.out
    assert "Port resources cleaned up" in out.out
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

    main([str(validation_integration), "--skip-cleanup", "--report", str(report_path)])

    assert "Port resources kept" in capsys.readouterr().out
    (client,) = fake_port_clients.values()
    assert client.names()[-1] == "mark_initialized"
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
        main([str(validation_integration)])

    assert exc_info.value.code == 2
    assert "sampleTeam" in capsys.readouterr().err
    assert fake_port_clients == {}


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
        main([str(validation_integration)])

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
        main([str(validation_integration)])

    assert exc_info.value.code == 2
    assert "OCEAN__INTEGRATION__TYPE" in capsys.readouterr().err
