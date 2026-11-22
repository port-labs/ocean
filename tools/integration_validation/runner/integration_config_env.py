from __future__ import annotations

import json
import os
import re
from typing import Any

from humps import decamelize

_MOCK_BASE_URL_TEMPLATE = re.compile(r"\{\{\s*mock_base_url\s*\}\}")

_INTEGRATION_CONFIG_ENV_PREFIX = "OCEAN__INTEGRATION__CONFIG__"

# Validation runs integrations in-process address-less mode; webhook/app URLs must
# not leak from the developer's .env into the subprocess.
_BLOCKED_SUBPROCESS_ENV_KEYS = frozenset(
    {
        "OCEAN__BASE_URL",
        "OCEAN__INTEGRATION__CONFIG__APP_HOST",
    }
)


def merge_scenario_integration_config(
    defaults: dict[str, Any],
    scenario_overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(defaults)
    if scenario_overrides:
        merged.update(scenario_overrides)
    return merged


def render_integration_config_values(
    config: dict[str, Any], *, mock_base_url: str
) -> dict[str, Any]:
    rendered: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            rendered[key] = _MOCK_BASE_URL_TEMPLATE.sub(mock_base_url, value)
        elif isinstance(value, dict):
            rendered[key] = render_integration_config_values(
                value, mock_base_url=mock_base_url
            )
        else:
            rendered[key] = value
    return rendered


def integration_config_env_vars(config: dict[str, Any]) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in config.items():
        if value is None:
            continue
        env_key = f"{_INTEGRATION_CONFIG_ENV_PREFIX}{decamelize(key).upper()}"
        if isinstance(value, (dict, list)):
            env[env_key] = _json_stringify(value)
        else:
            env[env_key] = str(value)
    return env


def build_sail_subprocess_env(
    *,
    integration_identifier: str,
    integration_config: dict[str, Any],
    mock_base_url: str,
) -> dict[str, str]:
    rendered = render_integration_config_values(
        integration_config, mock_base_url=mock_base_url
    )
    env = os.environ.copy()
    for blocked in _BLOCKED_SUBPROCESS_ENV_KEYS:
        env.pop(blocked, None)

    env["OCEAN__INTEGRATION__IDENTIFIER"] = integration_identifier
    env["OCEAN__INITIALIZE_PORT_RESOURCES"] = "false"
    env["OCEAN__EVENT_LISTENER__TYPE"] = "ONCE"
    env.update(integration_config_env_vars(rendered))
    return env


def _json_stringify(value: dict[str, Any] | list[Any]) -> str:
    return json.dumps(value)
