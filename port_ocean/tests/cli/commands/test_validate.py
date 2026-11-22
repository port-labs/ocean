"""Tests for the validate CLI command."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from port_ocean.cli.commands.validate import validate


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


def test_validate_help_lists_options() -> None:
    runner = CliRunner()
    result = runner.invoke(validate, ["--help"])
    assert result.exit_code == 0
    assert "--scenario" in result.output
    assert "--update-expected" in result.output
    assert "--keep" in result.output
    assert "--report" in result.output


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

    runner = CliRunner()
    result = runner.invoke(validate, [str(integration_root)])

    assert result.exit_code == 2
    assert "Setup error" in result.output
    assert "scenarios.yaml" in result.output


def test_validate_preflight_passes_for_minimal_suite(
    validation_integration: Path,
) -> None:
    runner = CliRunner()
    result = runner.invoke(validate, [str(validation_integration)])

    assert result.exit_code == 0
    assert "happy_path" in result.output
    assert "preflight checks passed" in result.output


def test_validate_missing_port_credentials_exits_2(
    validation_integration: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "OCEAN__PORT__CLIENT_ID",
        "OCEAN__PORT__CLIENT_SECRET",
        "OCEAN__PORT__BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    (validation_integration / ".env").unlink()

    runner = CliRunner()
    result = runner.invoke(validate, [str(validation_integration)])

    assert result.exit_code == 2
    assert "Missing Port credentials" in result.output
