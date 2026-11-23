from __future__ import annotations

import copy
import json
from typing import Any

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.naming import suffix_identifier

_RELATION_KEYS = ("relations", "teamInheritance", "ownership")
_DERIVED_PROPERTY_KEYS = (
    "calculationProperties",
    "mirrorProperties",
    "aggregationProperties",
)


def suffix_blueprints(
    blueprints: list[dict[str, Any]], scenario_name: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Copy blueprints with suffixed identifiers and rewritten in-set references.

    References to blueprints outside the set (for example ``_user``) are kept.
    """
    renames = {
        blueprint["identifier"]: suffix_identifier(
            blueprint["identifier"], scenario_name
        )
        for blueprint in blueprints
    }
    suffixed: list[dict[str, Any]] = []
    for blueprint in blueprints:
        rewritten = copy.deepcopy(blueprint)
        rewritten["identifier"] = renames[blueprint["identifier"]]
        for reference in _blueprint_references(rewritten):
            target = reference.get("target")
            if target in renames:
                reference["target"] = renames[target]
        suffixed.append(rewritten)
    return suffixed, renames


def rewrite_mapping_blueprints(
    port_app_config: dict[str, Any], renames: dict[str, str]
) -> dict[str, Any]:
    """Point every resource mapping at the suffixed blueprint identifiers.

    Only JQ string literals (``'"datadogTeam"'``) can be rewritten. Dynamic
    expressions or blueprints missing from the set would write outside the
    run's isolated blueprints, so they are rejected.
    """
    rewritten = copy.deepcopy(port_app_config)
    for resource in rewritten.get("resources") or []:
        kind = resource.get("kind", "<unknown>")
        mappings = resource.get("port", {}).get("entity", {}).get("mappings")
        mapping_list = mappings if isinstance(mappings, list) else [mappings]
        for mapping in mapping_list:
            if not isinstance(mapping, dict):
                raise ValidationSetupError(
                    f"port_app_config: kind '{kind}' has no port.entity.mappings"
                )
            mapping["blueprint"] = _rewrite_blueprint_expression(
                mapping.get("blueprint"), kind, renames
            )
    return rewritten


def blueprint_deletion_layers(blueprints: list[dict[str, Any]]) -> list[list[str]]:
    """Group identifiers so each layer is referenced only by earlier layers.

    Blueprints in one layer can be deleted concurrently. Reference cycles end
    up together in the last layer.
    """
    remaining = {blueprint["identifier"]: blueprint for blueprint in blueprints}
    layers: list[list[str]] = []
    while remaining:
        referenced = {
            reference.get("target")
            for identifier, blueprint in remaining.items()
            for reference in _blueprint_references(blueprint)
            if reference.get("target") != identifier
        }
        layer = [identifier for identifier in remaining if identifier not in referenced]
        if not layer:
            layers.append(list(remaining))
            break
        layers.append(layer)
        for identifier in layer:
            del remaining[identifier]
    return layers


def _blueprint_references(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for key in ("relations", "aggregationProperties"):
        section = blueprint.get(key) or {}
        references.extend(
            value for value in section.values() if isinstance(value, dict)
        )
    return references


def _without_keys(blueprint: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value) for key, value in blueprint.items() if key not in keys
    }


def _rewrite_blueprint_expression(
    expression: Any, kind: str, renames: dict[str, str]
) -> str:
    blueprint = _parse_jq_string_literal(expression)
    if blueprint is None:
        raise ValidationSetupError(
            f"port_app_config: kind '{kind}' maps to blueprint expression "
            f"{expression!r}. Only string literals such as '\"myBlueprint\"' "
            "can be isolated per run."
        )
    if blueprint not in renames:
        raise ValidationSetupError(
            f"port_app_config: kind '{kind}' maps to blueprint '{blueprint}', "
            "which is not defined in the scenario's blueprints file."
        )
    return json.dumps(renames[blueprint])


def _parse_jq_string_literal(expression: Any) -> str | None:
    if not isinstance(expression, str):
        return None
    stripped = expression.strip()
    if len(stripped) < 2 or not (stripped.startswith('"') and stripped.endswith('"')):
        return None
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, str) else None
