from pathlib import Path

import pytest

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.loader import load_scenarios_document


def test_load_scenarios_document_rejects_invalid_yaml(tmp_path: Path) -> None:
    scenarios_file = tmp_path / "scenarios.yaml"
    scenarios_file.write_text(
        """
defaults:
  port_app_config: .port/resources/port-app-config.yaml
scenarios:
  happy_path:
    routes: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationSetupError, match="scenarios.yaml"):
        load_scenarios_document(scenarios_file)


def test_load_scenarios_document_accepts_valid_file(tmp_path: Path) -> None:
    scenarios_file = tmp_path / "scenarios.yaml"
    scenarios_file.write_text(
        """
defaults:
  integration_config:
    exampleBaseUrl: "{{mock_base_url}}"
  port_app_config: .port/resources/port-app-config.yaml
  blueprints: .port/resources/blueprints.json
  ignore_fields: [createdAt]
scenarios:
  happy_path:
    description: Basic resync
    kinds: [team]
    routes: [routes/team.yaml]
    blueprints: validation/fixtures/blueprints.json
    expect:
      entities: expected/happy_path/
      unmatched_requests: none
""",
        encoding="utf-8",
    )

    document = load_scenarios_document(scenarios_file)

    assert document.defaults.integration_config["exampleBaseUrl"] == "{{mock_base_url}}"
    assert document.scenarios["happy_path"].kinds == ["team"]
    assert document.defaults.blueprints == ".port/resources/blueprints.json"
    assert (
        document.scenarios["happy_path"].blueprints
        == "validation/fixtures/blueprints.json"
    )
