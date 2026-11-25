import json
from pathlib import Path
from typing import Any

import pytest

from tools.integration_validation.runner.core.errors import ValidationSetupError
from tools.integration_validation.runner.core.models import (
    PortEntity,
    ScenarioDefinition,
    ValidationPaths,
)
from tools.integration_validation.runner.results.expected import (
    load_expected,
    resolve_expected_dir,
    write_expected,
)


def _entity(identifier: str, **fields: Any) -> PortEntity:
    return PortEntity.model_validate({"identifier": identifier, **fields})


@pytest.fixture
def paths(tmp_path: Path) -> ValidationPaths:
    validation_root = tmp_path / "sample" / "validation"
    return ValidationPaths(
        integration_root=tmp_path / "sample",
        validation_root=validation_root,
        scenarios_file=validation_root / "scenarios.yaml",
        mock_root=validation_root / "mock",
    )


def test_expected_dir_defaults_to_expected_scenario(paths: ValidationPaths) -> None:
    scenario = ScenarioDefinition(routes=["routes/team.yaml"])

    assert resolve_expected_dir(paths, "happy_path", scenario) == (
        paths.validation_root / "expected" / "happy_path"
    )


def test_expected_dir_uses_expect_entities_relative_to_validation(
    paths: ValidationPaths,
) -> None:
    scenario = ScenarioDefinition.model_validate(
        {"routes": ["r.yaml"], "expect": {"entities": "expected/happy_path/"}}
    )

    assert resolve_expected_dir(paths, "rate_limited", scenario) == (
        paths.validation_root / "expected" / "happy_path"
    )


def test_missing_or_empty_dir_means_no_snapshots(tmp_path: Path) -> None:
    assert load_expected(tmp_path / "missing") is None
    (tmp_path / "empty").mkdir()
    assert load_expected(tmp_path / "empty") is None


def test_write_then_load_round_trips_with_a_file_per_blueprint(
    tmp_path: Path,
) -> None:
    entities = {"team": [_entity("a", title="A")], "user": []}

    write_expected(tmp_path / "happy_path", entities)

    assert sorted(file.name for file in (tmp_path / "happy_path").iterdir()) == [
        "team.json",
        "user.json",
    ]
    assert (tmp_path / "happy_path" / "user.json").read_text() == "[]\n"
    assert load_expected(tmp_path / "happy_path") == entities


def test_all_empty_result_is_loaded_as_expecting_no_entities(tmp_path: Path) -> None:
    write_expected(tmp_path, {"team": [], "user": []})

    assert load_expected(tmp_path) == {"team": [], "user": []}


def test_write_removes_snapshots_of_blueprints_no_longer_in_the_result(
    tmp_path: Path,
) -> None:
    write_expected(tmp_path, {"team": [_entity("a")], "user": [_entity("u")]})

    write_expected(tmp_path, {"team": [_entity("a")]})

    assert sorted(file.name for file in tmp_path.iterdir()) == ["team.json"]


def test_snapshot_files_are_stable(tmp_path: Path) -> None:
    entities = {"team": [_entity("a", title="A", properties={"z": 1, "a": 2})]}

    write_expected(tmp_path, entities)
    first = (tmp_path / "team.json").read_text()
    write_expected(tmp_path, entities)

    assert (tmp_path / "team.json").read_text() == first
    assert first.endswith("\n")
    assert first.index('"identifier"') < first.index('"title"')
    assert first.index('"a": 2') < first.index('"z": 1')


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "Could not load"),
        (json.dumps({"identifier": "a"}), "JSON array"),
        (json.dumps(["a"]), "JSON array"),
        (json.dumps([{"title": "no identifier"}]), "JSON array"),
    ],
)
def test_invalid_snapshot_is_a_setup_error(
    tmp_path: Path, content: str, message: str
) -> None:
    (tmp_path / "team.json").write_text(content, encoding="utf-8")

    with pytest.raises(ValidationSetupError, match=message):
        load_expected(tmp_path)
