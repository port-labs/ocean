import json
from pathlib import Path

import pytest

from port_ocean.exceptions.spec import SpecFileError
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


def test_get_spec_file_raises_on_invalid_json(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.json").write_text("{invalid json")

    # Act + Assert
    with pytest.raises(SpecFileError, match="invalid JSON"):
        get_spec_file(tmp_path)


def test_get_spec_file_raises_on_invalid_yaml(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.yaml").write_text("key: [unclosed")

    # Act + Assert
    with pytest.raises(SpecFileError, match="invalid YAML"):
        get_spec_file(tmp_path)


def test_get_spec_file_raises_when_json_is_not_an_object(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.json").write_text(json.dumps(["not", "an", "object"]))

    # Act + Assert
    with pytest.raises(SpecFileError, match="must contain a JSON object"):
        get_spec_file(tmp_path)


def test_get_spec_file_raises_when_yaml_is_not_an_object(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.yaml").write_text("- item")

    # Act + Assert
    with pytest.raises(SpecFileError, match="must contain a JSON object"):
        get_spec_file(tmp_path)


def test_get_spec_file_raises_when_spec_file_is_empty(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / ".port"
    spec_dir.mkdir()
    (spec_dir / "spec.yaml").write_text("")

    # Act + Assert
    with pytest.raises(SpecFileError, match="must contain a JSON object"):
        get_spec_file(tmp_path)
