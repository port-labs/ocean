import json
from pathlib import Path

from port_ocean.utils.misc import get_spec_file


def test_get_spec_file_prefers_json_over_yaml(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.yaml").write_text("type: yaml")
    (spec_dir / "spec.json").write_text(json.dumps({"type": "json"}))

    # Act
    result = get_spec_file(tmp_path)

    # Assert
    assert result == {"type": "json"}


def test_get_spec_file_falls_back_to_yaml(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.yaml").write_text("type: yaml")

    # Act
    result = get_spec_file(tmp_path)

    # Assert
    assert result == {"type": "yaml"}


def test_get_spec_file_returns_none_when_missing(tmp_path: Path) -> None:
    # Act
    result = get_spec_file(tmp_path)

    # Assert
    assert result is None
