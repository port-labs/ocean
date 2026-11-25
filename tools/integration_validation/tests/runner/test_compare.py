from tools.integration_validation.runner.results.compare import (
    BlueprintDiff,
    FieldChange,
    diff_entities,
)


def _team(identifier: str, **properties: object) -> dict[str, object]:
    return {"identifier": identifier, "properties": properties}


def test_identical_entities_have_no_diff() -> None:
    entities = {"team": [_team("a", handle="a")]}

    assert diff_entities(entities, entities) == {}


def test_reports_added_removed_and_changed_entities() -> None:
    expected = {"team": [_team("a", handle="a"), _team("gone", handle="g")]}
    actual = {"team": [_team("a", handle=None), _team("extra", handle="e")]}

    assert diff_entities(expected, actual) == {
        "team": BlueprintDiff(
            added=["extra"],
            removed=["gone"],
            changed=[FieldChange("a", "properties.handle", "a", None)],
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

    changes = diff_entities(expected, actual)["team"].changed

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

    (change,) = diff_entities(expected, actual)["team"].changed

    assert (change.field, change.expected, change.actual) == (
        "properties.handle",
        "a",
        None,
    )


def test_blueprint_missing_on_one_side_counts_as_empty() -> None:
    diff = diff_entities({"user": [_team("u")]}, {"team": [_team("t")]})

    assert list(diff) == ["team", "user"]
    assert diff["team"].added == ["t"]
    assert diff["user"].removed == ["u"]


def test_diff_serializes_in_report_shape() -> None:
    diff = diff_entities({"team": [_team("a", handle="a")]}, {"team": [_team("a")]})

    assert diff["team"].to_dict() == {
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
