"""Field-by-field diff of normalized entities against expected snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldChange:
    identifier: str
    # Dotted path inside the entity, for example ``properties.handle``.
    field: str
    # ``None`` when the field is missing on that side.
    expected: Any
    actual: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class BlueprintDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[FieldChange] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": [change.to_dict() for change in self.changed],
        }


def diff_entities(
    expected: dict[str, list[dict[str, Any]]],
    actual: dict[str, list[dict[str, Any]]],
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
    expected: dict[str, dict[str, Any]], actual: dict[str, dict[str, Any]]
) -> BlueprintDiff:
    changed: list[FieldChange] = []
    for identifier in sorted(expected.keys() & actual.keys()):
        changed.extend(
            FieldChange(identifier, path, expected_value, actual_value)
            for path, expected_value, actual_value in _diff_values(
                expected[identifier], actual[identifier], ""
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
    if expected == actual:
        return []
    return [(path, expected, actual)]


def _is_object_or_missing(value: Any) -> bool:
    return value is None or isinstance(value, dict)


def _by_identifier(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entity.get("identifier")): entity for entity in entities}
