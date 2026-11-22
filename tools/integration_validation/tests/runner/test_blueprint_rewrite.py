import copy
from typing import Any

import pytest

from tools.integration_validation.runner.blueprint_rewrite import (
    blueprint_creation_stages,
    blueprint_deletion_layers,
    rewrite_mapping_blueprints,
    suffix_blueprints,
)
from tools.integration_validation.runner.errors import ValidationSetupError

BLUEPRINTS: list[dict[str, Any]] = [
    {"identifier": "user", "title": "User", "schema": {"properties": {}}},
    {
        "identifier": "team",
        "title": "Team",
        "schema": {"properties": {}},
        "relations": {
            "members": {"target": "user", "many": True},
            "owner": {"target": "_user", "many": False},
        },
        "mirrorProperties": {"ownerEmail": {"path": "owner.$identifier"}},
        "aggregationProperties": {
            "memberCount": {"target": "user", "calculationSpec": {"func": "count"}}
        },
        "ownership": {"type": "Direct"},
    },
]


def _mapping(blueprint_expression: str, kind: str = "team") -> dict[str, Any]:
    return {
        "kind": kind,
        "selector": {"query": "true"},
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".id",
                    "blueprint": blueprint_expression,
                    "relations": {"members": ".members"},
                }
            }
        },
    }


def test_suffix_blueprints_rewrites_identifiers_and_in_set_targets() -> None:
    suffixed, renames = suffix_blueprints(BLUEPRINTS, "a1b2")

    assert renames == {"user": "user-a1b2", "team": "team-a1b2"}
    team = suffixed[1]
    assert team["identifier"] == "team-a1b2"
    assert team["relations"]["members"]["target"] == "user-a1b2"
    assert team["aggregationProperties"]["memberCount"]["target"] == "user-a1b2"


def test_suffix_blueprints_keeps_targets_outside_the_set() -> None:
    suffixed, _ = suffix_blueprints(BLUEPRINTS, "a1b2")

    team = suffixed[1]
    assert team["relations"]["owner"]["target"] == "_user"
    assert team["mirrorProperties"] == {"ownerEmail": {"path": "owner.$identifier"}}


def test_suffix_blueprints_does_not_mutate_input() -> None:
    original = copy.deepcopy(BLUEPRINTS)

    suffix_blueprints(BLUEPRINTS, "a1b2")

    assert BLUEPRINTS == original


def test_rewrite_mapping_blueprints_rewrites_string_literals() -> None:
    config = {"resources": [_mapping('"team"'), _mapping(' "user" ', kind="user")]}

    rewritten = rewrite_mapping_blueprints(
        config, {"team": "team-a1b2", "user": "user-a1b2"}
    )

    blueprints = [
        resource["port"]["entity"]["mappings"]["blueprint"]
        for resource in rewritten["resources"]
    ]
    assert blueprints == ['"team-a1b2"', '"user-a1b2"']
    assert config["resources"][0]["port"]["entity"]["mappings"]["blueprint"] == '"team"'


def test_rewrite_mapping_blueprints_handles_mapping_lists() -> None:
    resource = _mapping('"team"')
    mapping = resource["port"]["entity"]["mappings"]
    resource["port"]["entity"]["mappings"] = [mapping, {**mapping}]

    rewritten = rewrite_mapping_blueprints(
        {"resources": [resource]}, {"team": "team-a1b2"}
    )

    mappings = rewritten["resources"][0]["port"]["entity"]["mappings"]
    assert [m["blueprint"] for m in mappings] == ['"team-a1b2"'] * 2


def test_rewrite_mapping_blueprints_rejects_dynamic_expressions() -> None:
    config = {"resources": [_mapping('if .x then "a" else "b" end')]}

    with pytest.raises(ValidationSetupError, match="Only string literals"):
        rewrite_mapping_blueprints(config, {"team": "team-a1b2"})


def test_rewrite_mapping_blueprints_rejects_blueprints_outside_the_set() -> None:
    config = {"resources": [_mapping('"service"')]}

    with pytest.raises(ValidationSetupError, match="'service'"):
        rewrite_mapping_blueprints(config, {"team": "team-a1b2"})


def test_blueprint_creation_stages_strip_relations_then_derived_properties() -> None:
    bare, with_relations, full = blueprint_creation_stages(BLUEPRINTS)

    assert set(bare[1]) == {"identifier", "title", "schema"}
    assert set(with_relations[1]) == {
        "identifier",
        "title",
        "schema",
        "relations",
        "ownership",
    }
    assert full[1] == BLUEPRINTS[1]
    assert "relations" in BLUEPRINTS[1]


def test_blueprint_deletion_layers_delete_dependents_first() -> None:
    blueprints: list[dict[str, Any]] = [
        {"identifier": "a"},
        {"identifier": "b", "relations": {"toA": {"target": "a"}}},
        {"identifier": "c", "relations": {"toB": {"target": "b"}}},
        {"identifier": "d", "aggregationProperties": {"n": {"target": "a"}}},
    ]

    assert blueprint_deletion_layers(blueprints) == [["c", "d"], ["b"], ["a"]]


def test_blueprint_deletion_layers_ignore_self_relations_and_group_cycles() -> None:
    blueprints: list[dict[str, Any]] = [
        {"identifier": "self", "relations": {"parent": {"target": "self"}}},
        {"identifier": "x", "relations": {"toY": {"target": "y"}}},
        {"identifier": "y", "relations": {"toX": {"target": "x"}}},
    ]

    assert blueprint_deletion_layers(blueprints) == [["self"], ["x", "y"]]
