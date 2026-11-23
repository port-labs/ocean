"""Tests for the integration validation runner CLI."""

from pathlib import Path

import pytest

from tools.integration_validation.runner.main import main


@pytest.fixture
def validation_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    integration_root = tmp_path / "sample"
    validation_root = integration_root / "validation"
    mock_root = validation_root / "mock"
    mock_root.mkdir(parents=True)
    (integration_root / ".port" / "resources").mkdir(parents=True)
    (integration_root / ".port" / "resources" / "port-app-config.yaml").write_text(
        "resources: []\n",
        encoding="utf-8",
    )
    (integration_root / ".port" / "resources" / "blueprints.json").write_text(
        "[]\n",
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


def test_validate_preflight_passes_for_minimal_suite(
    validation_integration: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(validation_integration)])
    out = capsys.readouterr()
    assert "happy_path" in out.out
    assert "preflight checks passed" in out.err


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
