"""Reduce Port entities to the fields a snapshot should compare."""

from __future__ import annotations

import copy
from typing import Any

# Set by Port, not by the mapping. ``blueprint`` carries the run suffix; the
# expected file name already records the real blueprint.
PORT_MANAGED_FIELDS = ("blueprint", "createdAt", "updatedAt", "createdBy", "updatedBy")

# Sections whose null values are dropped so that null and missing compare equal;
# a section left empty is dropped too.
NULLABLE_SECTIONS = ("properties", "relations")


def normalize_blueprint_entities(
    entities: list[dict[str, Any]], ignore_fields: list[str]
) -> list[dict[str, Any]]:
    normalized = [normalize_entity(entity, ignore_fields) for entity in entities]
    return sorted(normalized, key=lambda entity: str(entity.get("identifier")))


def normalize_entity(
    entity: dict[str, Any], ignore_fields: list[str]
) -> dict[str, Any]:
    normalized = copy.deepcopy(entity)
    for field in PORT_MANAGED_FIELDS:
        normalized.pop(field, None)
    for field in ignore_fields:
        _drop_path(normalized, field.split("."))

    for section in NULLABLE_SECTIONS:
        values = normalized.get(section)
        if not isinstance(values, dict):
            continue
        values = _without_nulls(values)
        if values:
            normalized[section] = values
        else:
            del normalized[section]

    relations = normalized.get("relations")
    if isinstance(relations, dict):
        normalized["relations"] = {
            name: _sorted_if_list(value) for name, value in relations.items()
        }
    if "team" in normalized:
        normalized["team"] = _sorted_if_list(normalized["team"])

    return _without_nulls(normalized)


def _drop_path(target: dict[str, Any], path: list[str]) -> None:
    head, *rest = path
    if not rest:
        target.pop(head, None)
        return
    child = target.get(head)
    if isinstance(child, dict):
        _drop_path(child, rest)


def _without_nulls(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _sorted_if_list(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(value, key=str)
    return value
