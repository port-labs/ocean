import json
from pathlib import Path
from typing import Any

from tools.integration_validation.runner.core.models import PortEntity
from tools.integration_validation.runner.core.statuses import ComparisonStatus
from tools.integration_validation.runner.results.evaluate import (
    ScenarioComparison,
    evaluate_scenario,
)

TEAM = {
    "identifier": "platform",
    "blueprint": "team-happy-path",
    "properties": {"handle": "platform", "description": None},
    "createdAt": "2026-11-25T08:00:00Z",
}


def _evaluate(
    expected_dir: Path,
    entities: dict[str, list[dict[str, Any]]],
    **overrides: Any,
) -> ScenarioComparison:
    options: dict[str, Any] = {
        "expected_dir": expected_dir,
        "ignore_fields": [],
        "update_expected": False,
        "resync_succeeded": True,
    }
    options.update(overrides)
    parsed = {
        blueprint: [PortEntity.model_validate(entity) for entity in blueprint_entities]
        for blueprint, blueprint_entities in entities.items()
    }
    return evaluate_scenario(parsed, **options)


def test_first_run_writes_normalized_snapshots_and_is_new(tmp_path: Path) -> None:
    comparison = _evaluate(tmp_path, {"team": [TEAM]})

    assert comparison.status == ComparisonStatus.NEW
    assert comparison.passed
    assert json.loads((tmp_path / "team.json").read_text()) == [
        {"identifier": "platform", "properties": {"handle": "platform"}}
    ]


def test_rerun_with_same_result_matches(tmp_path: Path) -> None:
    _evaluate(tmp_path, {"team": [TEAM]})

    comparison = _evaluate(tmp_path, {"team": [TEAM]})

    assert comparison.status == ComparisonStatus.MATCHED
    assert comparison.entity_diff == {}


def test_changed_result_is_different_and_leaves_snapshots_alone(
    tmp_path: Path,
) -> None:
    _evaluate(tmp_path, {"team": [TEAM]})
    snapshot = (tmp_path / "team.json").read_text()

    comparison = _evaluate(
        tmp_path, {"team": [{**TEAM, "properties": {"handle": None}}]}
    )

    assert comparison.status == ComparisonStatus.DIFFERENT
    assert comparison.difference_count == 1
    assert not comparison.passed
    (change,) = comparison.entity_diff["team"].changed
    assert (change.field, change.expected, change.actual) == (
        "properties.handle",
        "platform",
        None,
    )
    assert (tmp_path / "team.json").read_text() == snapshot


def test_update_expected_overwrites_snapshots(tmp_path: Path) -> None:
    _evaluate(tmp_path, {"team": [TEAM]})

    comparison = _evaluate(
        tmp_path, {"team": [{**TEAM, "title": "Platform"}]}, update_expected=True
    )

    assert comparison.status == ComparisonStatus.UPDATED
    assert comparison.passed
    assert json.loads((tmp_path / "team.json").read_text())[0]["title"] == "Platform"


def test_failed_resync_never_writes_snapshots(tmp_path: Path) -> None:
    comparison = _evaluate(tmp_path, {"team": [TEAM]}, resync_succeeded=False)

    assert comparison.status == ComparisonStatus.SKIPPED
    assert not comparison.passed
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_hand_edited_snapshots_are_normalized_before_diffing(tmp_path: Path) -> None:
    (tmp_path / "team.json").write_text(
        json.dumps(
            [
                {
                    "identifier": "platform",
                    "properties": {"handle": "platform", "lastSeen": "x"},
                    "relations": {"lead": None},
                }
            ]
        ),
        encoding="utf-8",
    )

    comparison = _evaluate(
        tmp_path, {"team": [TEAM]}, ignore_fields=["properties.lastSeen"]
    )

    assert comparison.status == ComparisonStatus.MATCHED


def test_all_empty_first_run_is_still_an_expectation(tmp_path: Path) -> None:
    first = _evaluate(tmp_path, {"team": [], "user": []})

    later = _evaluate(tmp_path, {"team": [TEAM], "user": []})

    assert first.status == ComparisonStatus.NEW
    assert later.status == ComparisonStatus.DIFFERENT
    assert later.entity_diff["team"].added == ["platform"]
    assert json.loads((tmp_path / "team.json").read_text()) == []


def test_comparison_serializes_in_report_shape(tmp_path: Path) -> None:
    _evaluate(tmp_path, {"team": [TEAM]})

    comparison = _evaluate(tmp_path, {"team": []})

    assert comparison.model_dump(mode="json") == {
        "status": "different",
        "expected_dir": str(tmp_path),
        "entity_diff": {"team": {"added": [], "removed": ["platform"], "changed": []}},
    }
