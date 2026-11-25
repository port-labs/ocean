"""Field-by-field diff of normalized entities against expected snapshots."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from tools.integration_validation.runner.core.models import (
    EntitiesByBlueprint,
    PortEntity,
)


class FieldChange(BaseModel):
    model_config = ConfigDict(frozen=True)

    identifier: str
    # Dotted path inside the entity, for example ``properties.handle``.
    field: str
    # ``None`` when the field is missing on that side.
    expected: JsonValue
    actual: JsonValue


class BlueprintDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: list[FieldChange] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def diff_entities(
    expected: EntitiesByBlueprint, actual: EntitiesByBlueprint
) -> dict[str, BlueprintDiff]:
    """Diff per blueprint; blueprints without differences are left out.

    Both sides must already be normalized. A blueprint missing on one side is
    treated as having no entities there.
    """
    diffs: dict[str, BlueprintDiff] = {}
    for blueprint in sorted(expected.keys() | actual.keys()):
        diff = _diff_blueprint(
            _by_identifier(expected.get(blueprint, [])),
            _by_identifier(actual.get(blueprint, [])),
        )
        if not diff.is_empty:
            diffs[blueprint] = diff
    return diffs


def _diff_blueprint(
    expected: dict[str, PortEntity], actual: dict[str, PortEntity]
) -> BlueprintDiff:
    changed: list[FieldChange] = []
    for identifier in sorted(expected.keys() & actual.keys()):
        changed.extend(
            FieldChange(
                identifier=identifier,
                field=path,
                expected=expected_value,
                actual=actual_value,
            )
            for path, expected_value, actual_value in _diff_values(
                expected[identifier].as_json(), actual[identifier].as_json(), ""
            )
        )
    return BlueprintDiff(
        added=sorted(actual.keys() - expected.keys()),
        removed=sorted(expected.keys() - actual.keys()),
        changed=changed,
    )


def _diff_values(expected: Any, actual: Any, path: str) -> list[tuple[str, Any, Any]]:
    # A missing object (``None``) diffs as an empty one, so changes stay at leaf paths.
    if _is_object_or_missing(expected) and _is_object_or_missing(actual):
        expected_object: dict[str, Any] = expected or {}
        actual_object: dict[str, Any] = actual or {}
        differences: list[tuple[str, Any, Any]] = []
        for key in sorted(expected_object.keys() | actual_object.keys()):
            child_path = f"{path}.{key}" if path else key
            differences.extend(
                _diff_values(
                    expected_object.get(key), actual_object.get(key), child_path
                )
            )
        return differences
    if _json_equal(expected, actual):
        return []
    return [(path, expected, actual)]


def _json_equal(left: Any, right: Any) -> bool:
    """``==`` for JSON values, except booleans never equal numbers.

    Python treats ``True == 1`` and ``False == 0``, which would hide a mapping
    that turned a boolean property into a number.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(_json_equal, left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _json_equal(value, right[key]) for key, value in left.items()
        )
    return bool(left == right)


def _is_object_or_missing(value: Any) -> bool:
    return value is None or isinstance(value, dict)


def _by_identifier(entities: list[PortEntity]) -> dict[str, PortEntity]:
    return {entity.identifier: entity for entity in entities}
