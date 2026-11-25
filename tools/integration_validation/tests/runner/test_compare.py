from typing import Any

from tools.integration_validation.runner.core.models import (
    EntitiesByBlueprint,
    PortEntity,
)
from tools.integration_validation.runner.results.compare import (
    BlueprintDiff,
    FieldChange,
    diff_entities,
)


def _team(identifier: str, **properties: Any) -> dict[str, Any]:
    return {"identifier": identifier, "properties": properties}


def _diff(
    expected: dict[str, list[dict[str, Any]]], actual: dict[str, list[dict[str, Any]]]
) -> dict[str, BlueprintDiff]:
    return diff_entities(_parse(expected), _parse(actual))


def _parse(entities: dict[str, list[dict[str, Any]]]) -> EntitiesByBlueprint:
    return {
        blueprint: [PortEntity.model_validate(entity) for entity in blueprint_entities]
        for blueprint, blueprint_entities in entities.items()
    }


def test_identical_entities_have_no_diff() -> None:
    entities = {"team": [_team("a", handle="a")]}

    assert _diff(entities, entities) == {}


def test_reports_added_removed_and_changed_entities() -> None:
    expected = {"team": [_team("a", handle="a"), _team("gone", handle="g")]}
    actual = {"team": [_team("a", handle=None), _team("extra", handle="e")]}

    assert _diff(expected, actual) == {
        "team": BlueprintDiff(
            added=["extra"],
            removed=["gone"],
            changed=[
                FieldChange(
                    identifier="a",
                    field="properties.handle",
                    expected="a",
                    actual=None,
                )
            ],
        )
    }


def test_changes_are_reported_at_leaf_paths_in_stable_order() -> None:
    expected = {
        "team": [
            {
                "identifier": "a",
                "title": "A",
                "properties": {"meta": {"owner": "x", "tier": 1}, "zeta": 1},
                "relations": {"members": ["u1"]},
            }
        ]
    }
    actual = {
        "team": [
            {
                "identifier": "a",
                "title": "A2",
                "properties": {"meta": {"owner": "y", "tier": 1}, "new": True},
                "relations": {"members": ["u1", "u2"]},
            }
        ]
    }

    changes = _diff(expected, actual)["team"].changed

    assert [(c.field, c.expected, c.actual) for c in changes] == [
        ("properties.meta.owner", "x", "y"),
        ("properties.new", None, True),
        ("properties.zeta", 1, None),
        ("relations.members", ["u1"], ["u1", "u2"]),
        ("title", "A", "A2"),
    ]


def test_missing_section_diffs_as_empty_object() -> None:
    expected = {"team": [{"identifier": "a", "properties": {"handle": "a"}}]}
    actual = {"team": [{"identifier": "a"}]}

    (change,) = _diff(expected, actual)["team"].changed

    assert (change.field, change.expected, change.actual) == (
        "properties.handle",
        "a",
        None,
    )


def test_blueprint_missing_on_one_side_counts_as_empty() -> None:
    diff = _diff({"user": [_team("u")]}, {"team": [_team("t")]})

    assert list(diff) == ["team", "user"]
    assert diff["team"].added == ["t"]
    assert diff["user"].removed == ["u"]


def test_diff_serializes_in_report_shape() -> None:
    diff = _diff({"team": [_team("a", handle="a")]}, {"team": [_team("a")]})

    assert diff["team"].model_dump(mode="json") == {
        "added": [],
        "removed": [],
        "changed": [
            {
                "identifier": "a",
                "field": "properties.handle",
                "expected": "a",
                "actual": None,
            }
        ],
    }


def test_booleans_never_match_numbers() -> None:
    expected = {"team": [_team("a", on=True, off=False, flags=[True, False])]}
    actual = {"team": [_team("a", on=1, off=0, flags=[1, 0])]}

    changes = _diff(expected, actual)["team"].changed

    assert [(c.field, c.expected, c.actual) for c in changes] == [
        ("properties.flags", [True, False], [1, 0]),
        ("properties.off", False, 0),
        ("properties.on", True, 1),
    ]


def test_booleans_nested_in_arrays_of_objects_are_compared_strictly() -> None:
    expected = {"team": [_team("a", rules=[{"enabled": True}])]}
    actual = {"team": [_team("a", rules=[{"enabled": 1}])]}

    (change,) = _diff(expected, actual)["team"].changed

    assert change.field == "properties.rules"


def test_equal_numbers_still_match_across_int_and_float() -> None:
    entities = {"team": [_team("a", count=1)]}

    assert _diff(entities, {"team": [_team("a", count=1.0)]}) == {}
