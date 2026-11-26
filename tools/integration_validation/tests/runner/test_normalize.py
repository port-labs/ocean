from typing import Any

from tools.integration_validation.runner.core.models import PortEntity
from tools.integration_validation.runner.results.normalize import (
    normalize_blueprint_entities,
    normalize_entity,
)


def _port_entity(**overrides: Any) -> PortEntity:
    entity: dict[str, Any] = {
        "identifier": "platform",
        "title": "Platform",
        "blueprint": "datadogTeam-happy-path",
        "team": ["b", "a"],
        "properties": {"handle": "platform", "description": None},
        "relations": {"members": ["zoe", "adam"], "lead": None, "org": "acme"},
        "createdAt": "2026-11-25T08:00:00Z",
        "updatedAt": "2026-11-25T08:00:00Z",
        "createdBy": "client-id",
        "updatedBy": "client-id",
    }
    entity.update(overrides)
    return PortEntity.model_validate(entity)


def _normalize(entity: PortEntity, ignore_fields: list[str]) -> dict[str, Any]:
    return normalize_entity(entity, ignore_fields).model_dump(exclude_unset=True)


def test_drops_port_metadata_and_the_suffixed_blueprint() -> None:
    normalized = _normalize(_port_entity(), [])

    for field in ("blueprint", "createdAt", "updatedAt", "createdBy", "updatedBy"):
        assert field not in normalized


def test_keeps_explicit_null_property_and_relation_values() -> None:
    normalized = _normalize(_port_entity(), [])

    assert normalized["properties"] == {"handle": "platform", "description": None}
    assert normalized["relations"] == {
        "members": ["adam", "zoe"],
        "lead": None,
        "org": "acme",
    }


def test_null_property_key_is_not_equal_to_a_missing_key() -> None:
    with_null = _normalize(_port_entity(), [])
    without = _normalize(
        _port_entity(properties={"handle": "platform"}),
        [],
    )

    assert with_null != without
    assert "description" not in without["properties"]


def test_sorts_relation_arrays_and_team_but_not_property_arrays() -> None:
    normalized = _normalize(_port_entity(properties={"tags": ["z", "a"]}), [])

    assert normalized["relations"]["members"] == ["adam", "zoe"]
    assert normalized["team"] == ["a", "b"]
    assert normalized["properties"]["tags"] == ["z", "a"]


def test_single_team_string_becomes_a_list() -> None:
    normalized = _normalize(_port_entity(team="platform"), [])

    assert normalized["team"] == ["platform"]


def test_ignore_fields_supports_top_level_and_dotted_paths() -> None:
    normalized = _normalize(
        _port_entity(properties={"handle": "platform", "lastSeen": "now"}),
        ["title", "properties.lastSeen", "properties.missing.deep"],
    )

    assert "title" not in normalized
    assert normalized["properties"] == {"handle": "platform"}


def test_does_not_mutate_the_collected_entity() -> None:
    entity = _port_entity()

    normalize_entity(entity, ["properties.handle"])

    assert entity.blueprint == "datadogTeam-happy-path"
    assert entity.properties == {"handle": "platform", "description": None}


def test_blueprint_entities_are_sorted_by_identifier() -> None:
    normalized = normalize_blueprint_entities(
        [_port_entity(identifier="b"), _port_entity(identifier="a")], []
    )

    assert [entity.identifier for entity in normalized] == ["a", "b"]
