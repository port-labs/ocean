from __future__ import annotations

import copy
from typing import Any

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.models import ScenarioDefinition


def build_scenario_port_app_config(
    base_config: dict[str, Any],
    scenario_name: str,
    scenario: ScenarioDefinition,
) -> dict[str, Any]:
    """Apply a scenario's ``kinds`` filter and ``port_app_config_overrides``.

    Each override is deep-merged into every resource with the same ``kind``:
    mappings merge key by key, while lists and scalar values are replaced.
    """
    config = copy.deepcopy(base_config)
    resources: list[dict[str, Any]] = config.get("resources") or []

    if scenario.kinds:
        configured_kinds = {resource.get("kind") for resource in resources}
        missing = [kind for kind in scenario.kinds if kind not in configured_kinds]
        if missing:
            raise ValidationSetupError(
                f"Scenario '{scenario_name}': kinds {missing} have no resource "
                "in port_app_config."
            )
        resources = [
            resource for resource in resources if resource.get("kind") in scenario.kinds
        ]

    for override in scenario.port_app_config_overrides or []:
        kind = override.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValidationSetupError(
                f"Scenario '{scenario_name}': every port_app_config_overrides "
                "entry needs a 'kind'."
            )
        matched = False
        for index, resource in enumerate(resources):
            if resource.get("kind") == kind:
                resources[index] = _deep_merge(resource, override)
                matched = True
        if not matched:
            raise ValidationSetupError(
                f"Scenario '{scenario_name}': override for kind '{kind}' matches "
                "no resource in port_app_config (after filtering by the "
                "scenario's kinds)."
            )

    config["resources"] = resources
    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged
