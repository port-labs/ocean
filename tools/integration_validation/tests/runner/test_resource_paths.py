from pathlib import Path

import pytest

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.loader import (
    load_integration_type,
    load_scenarios_document,
    resolve_scenario_blueprints_path,
)
from tools.integration_validation.runner.models import ValidationPaths


def _validation_paths(integration_root: Path) -> ValidationPaths:
    return ValidationPaths(
        integration_root=integration_root,
        validation_root=integration_root / "validation",
        scenarios_file=integration_root / "validation" / "scenarios.yaml",
        mock_root=integration_root / "validation" / "mock",
    )


def test_resolve_scenario_blueprints_uses_defaults(tmp_path: Path) -> None:
    integration_root = tmp_path / "sample"
    resources = integration_root / ".port" / "resources"
    resources.mkdir(parents=True)
    (resources / "blueprints.json").write_text("[]\n", encoding="utf-8")
    (resources / "port-app-config.yaml").write_text("resources: []\n", encoding="utf-8")

    scenarios_file = integration_root / "validation" / "scenarios.yaml"
    scenarios_file.parent.mkdir(parents=True)
    scenarios_file.write_text(
        """
defaults:
  port_app_config: .port/resources/port-app-config.yaml
scenarios:
  happy_path:
    routes: [routes/team.yaml]
""",
        encoding="utf-8",
    )
    document = load_scenarios_document(scenarios_file)
    scenario = document.scenarios["happy_path"]

    resolved = resolve_scenario_blueprints_path(
        _validation_paths(integration_root), document.defaults, scenario
    )

    assert resolved == resources / "blueprints.json"


def test_resolve_scenario_blueprints_honors_scenario_override(tmp_path: Path) -> None:
    integration_root = tmp_path / "sample"
    resources = integration_root / ".port" / "resources"
    resources.mkdir(parents=True)
    (resources / "blueprints.json").write_text("[]\n", encoding="utf-8")
    custom = integration_root / "validation" / "fixtures" / "blueprints.json"
    custom.parent.mkdir(parents=True)
    custom.write_text("[]\n", encoding="utf-8")

    scenarios_file = integration_root / "validation" / "scenarios.yaml"
    scenarios_file.parent.mkdir(parents=True, exist_ok=True)
    scenarios_file.write_text(
        """
defaults:
  port_app_config: .port/resources/port-app-config.yaml
scenarios:
  service_dependency:
    blueprints: validation/fixtures/blueprints.json
    routes: [routes/deps.yaml]
""",
        encoding="utf-8",
    )
    document = load_scenarios_document(scenarios_file)
    scenario = document.scenarios["service_dependency"]

    resolved = resolve_scenario_blueprints_path(
        _validation_paths(integration_root), document.defaults, scenario
    )

    assert resolved == custom


def test_resolve_scenario_blueprints_missing_file_raises(tmp_path: Path) -> None:
    integration_root = tmp_path / "sample"
    scenarios_file = integration_root / "validation" / "scenarios.yaml"
    scenarios_file.parent.mkdir(parents=True)
    scenarios_file.write_text(
        """
defaults:
  port_app_config: .port/resources/port-app-config.yaml
scenarios:
  happy_path:
    routes: [routes/team.yaml]
""",
        encoding="utf-8",
    )
    document = load_scenarios_document(scenarios_file)
    scenario = document.scenarios["happy_path"]

    with pytest.raises(ValidationSetupError, match="blueprints not found"):
        resolve_scenario_blueprints_path(
            _validation_paths(integration_root), document.defaults, scenario
        )


def test_load_integration_type_reads_spec(tmp_path: Path) -> None:
    integration_root = tmp_path / "sample"
    (integration_root / ".port").mkdir(parents=True)
    (integration_root / ".port" / "spec.yaml").write_text(
        "type: sample\n", encoding="utf-8"
    )

    assert load_integration_type(_validation_paths(integration_root)) == "sample"


def test_load_integration_type_requires_spec(tmp_path: Path) -> None:
    integration_root = tmp_path / "sample"
    integration_root.mkdir()

    with pytest.raises(ValidationSetupError, match="integration type"):
        load_integration_type(_validation_paths(integration_root))
