from pathlib import Path

import pytest

from tools.integration_validation.runner.core.errors import ValidationSetupError
from tools.integration_validation.runner.scenarios.loader import load_blueprints_file
from tools.integration_validation.runner.core.models import BlueprintsDocument


def test_load_blueprints_file_parses_valid_json(tmp_path: Path) -> None:
    blueprints_file = tmp_path / "blueprints.json"
    blueprints_file.write_text(
        """
[
  {
    "identifier": "team",
    "title": "Team",
    "schema": {"properties": {}}
  }
]
""",
        encoding="utf-8",
    )

    document = load_blueprints_file(blueprints_file)

    assert isinstance(document, BlueprintsDocument)
    assert document.root[0].identifier == "team"
    assert document.as_mappings()[0]["title"] == "Team"


def test_load_blueprints_file_allows_empty_array(tmp_path: Path) -> None:
    blueprints_file = tmp_path / "blueprints.json"
    blueprints_file.write_text("[]", encoding="utf-8")

    document = load_blueprints_file(blueprints_file)

    assert document.root == []


def test_load_blueprints_file_rejects_missing_identifier(tmp_path: Path) -> None:
    blueprints_file = tmp_path / "blueprints.json"
    blueprints_file.write_text('[{"title": "Team"}]', encoding="utf-8")

    with pytest.raises(ValidationSetupError, match="0.identifier"):
        load_blueprints_file(blueprints_file)


def test_load_blueprints_file_rejects_non_array_root(tmp_path: Path) -> None:
    blueprints_file = tmp_path / "blueprints.json"
    blueprints_file.write_text('{"identifier": "team"}', encoding="utf-8")

    with pytest.raises(ValidationSetupError, match=str(blueprints_file)):
        load_blueprints_file(blueprints_file)
