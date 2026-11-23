from pathlib import Path

import pytest

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.loader import load_port_app_config_file
from tools.integration_validation.runner.models import PortAppConfigDocument


def test_load_port_app_config_file_parses_valid_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "port-app-config.yaml"
    config_file.write_text(
        """
deleteDependentEntities: true
resources:
  - kind: team
    selector:
      query: "true"
    port:
      entity:
        mappings:
          blueprint: '"team"'
""",
        encoding="utf-8",
    )

    document = load_port_app_config_file(config_file)

    assert isinstance(document, PortAppConfigDocument)
    assert document.resources[0].kind == "team"
    assert document.as_mapping()["deleteDependentEntities"] is True


def test_load_port_app_config_file_rejects_missing_kind(tmp_path: Path) -> None:
    config_file = tmp_path / "port-app-config.yaml"
    config_file.write_text(
        """
resources:
  - selector:
      query: "true"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationSetupError, match="resources.0.kind"):
        load_port_app_config_file(config_file)


def test_load_port_app_config_file_rejects_missing_resources(tmp_path: Path) -> None:
    config_file = tmp_path / "port-app-config.yaml"
    config_file.write_text("deleteDependentEntities: true\n", encoding="utf-8")

    with pytest.raises(ValidationSetupError, match="resources"):
        load_port_app_config_file(config_file)
