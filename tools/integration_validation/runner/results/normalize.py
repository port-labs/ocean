"""Reduce Port entities to the fields a snapshot should compare."""

from __future__ import annotations

from typing import Any

from tools.integration_validation.runner.core.models import (
    EntitiesByBlueprint,
    PortEntity,
)

# Set by Port, not by the mapping. ``blueprint`` carries the run suffix; the
# expected file name already records the real blueprint.
PORT_MANAGED_FIELDS = {"blueprint", "createdAt", "updatedAt", "createdBy", "updatedBy"}


def normalize_entities(
    entities: EntitiesByBlueprint, ignore_fields: list[str]
) -> EntitiesByBlueprint:
    return {
        blueprint: normalize_blueprint_entities(blueprint_entities, ignore_fields)
        for blueprint, blueprint_entities in entities.items()
    }


def normalize_blueprint_entities(
    entities: list[PortEntity], ignore_fields: list[str]
) -> list[PortEntity]:
    normalized = [normalize_entity(entity, ignore_fields) for entity in entities]
    return sorted(normalized, key=lambda entity: entity.identifier)


def normalize_entity(entity: PortEntity, ignore_fields: list[str]) -> PortEntity:
    normalized = entity.model_dump(exclude_unset=True, exclude=PORT_MANAGED_FIELDS)
    for field in ignore_fields:
        _drop_path(normalized, field.split("."))

    relations = normalized.get("relations")
    if relations is not None:
        normalized["relations"] = {
            name: _sorted_if_list(value) for name, value in relations.items()
        }
    if normalized.get("team") is not None:
        normalized["team"] = sorted(normalized["team"])

    return PortEntity.model_validate(normalized)


def _drop_path(target: dict[str, Any], path: list[str]) -> None:
    head, *rest = path
    if not rest:
        target.pop(head, None)
        return
    child = target.get(head)
    if isinstance(child, dict):
        _drop_path(child, rest)


def _sorted_if_list(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(value, key=str)
    return value
