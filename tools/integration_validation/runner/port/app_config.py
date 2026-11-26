from __future__ import annotations

import copy
from typing import Any

from tools.integration_validation.runner.core.errors import ValidationSetupError
from tools.integration_validation.runner.core.models import (
    PortAppConfigDocument,
    PortAppConfigOverride,
    PortAppConfigResource,
    ScenarioDefinition,
)


def build_scenario_port_app_config(
    base_config: PortAppConfigDocument,
    scenario_name: str,
    scenario: ScenarioDefinition,
) -> PortAppConfigDocument:
    """Apply a scenario's ``kinds`` filter and ``port_app_config_overrides``.

    Each override is deep-merged into every resource with the same ``kind``:
    mappings merge key by key, while lists and scalar values are replaced.
    """
    config = base_config.model_copy(deep=True)
    resources = config.resources

    if scenario.kinds:
        configured_kinds = {resource.kind for resource in resources}
        missing = [kind for kind in scenario.kinds if kind not in configured_kinds]
        if missing:
            raise ValidationSetupError(
                f"Scenario '{scenario_name}': kinds {missing} have no resource "
                "in port_app_config."
            )
        resources = [
            resource for resource in resources if resource.kind in scenario.kinds
        ]

    for override in scenario.port_app_config_overrides or []:
        matched = [resource for resource in resources if resource.kind == override.kind]
        if not matched:
            raise ValidationSetupError(
                f"Scenario '{scenario_name}': override for kind '{override.kind}' "
                "matches no resource in port_app_config (after filtering by the "
                "scenario's kinds)."
            )
        for resource in matched:
            _merge_override(resource, override)

    config.resources = resources
    return config


def _merge_override(
    resource: PortAppConfigResource, override: PortAppConfigOverride
) -> None:
    """Deep-merge an override's fields into ``resource`` in place.

    Iterating the override model yields its declared fields and its extras;
    ``setattr`` writes unknown keys straight into the resource's extras.
    """
    for key, value in override:
        current = getattr(resource, key, None)
        if isinstance(value, dict) and isinstance(current, dict):
            _deep_merge(current, value)
        else:
            setattr(resource, key, copy.deepcopy(value))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        current = base.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            _deep_merge(current, value)
        else:
            base[key] = copy.deepcopy(value)
