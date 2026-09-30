from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIGSETS_DIR = Path(__file__).parent / "configsets"


@dataclass(frozen=True)
class SmokeConfigSet:
    name: str
    wait_for_resync: bool
    ocean: dict[str, Any]


def list_configset_names() -> list[str]:
    return sorted(path.stem for path in CONFIGSETS_DIR.glob("*.yaml"))


def load_configset(name: str) -> SmokeConfigSet:
    path = CONFIGSETS_DIR / f"{name}.yaml"
    if not path.is_file():
        available = ", ".join(list_configset_names()) or "(none)"
        raise ValueError(f"Unknown smoke configset '{name}'. Available: {available}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid smoke configset '{name}': expected a mapping")
    ocean = raw.get("ocean", {})
    if not isinstance(ocean, dict):
        raise ValueError(f"Invalid smoke configset '{name}': ocean must be a mapping")
    wait_for_resync = raw["wait_for_resync"] if "wait_for_resync" in raw else True
    if not isinstance(wait_for_resync, bool):
        raise ValueError(
            f"Invalid smoke configset '{name}': wait_for_resync must be a boolean"
        )
    return SmokeConfigSet(
        name=name,
        wait_for_resync=wait_for_resync,
        ocean=ocean,
    )


def ocean_config_env(config: dict[str, Any], prefix: str = "OCEAN") -> dict[str, str]:
    """Flatten Ocean config into ``OCEAN__*`` env vars.

    ``event_listener`` is one JSON value (union selected by ``type``).
    """
    env: dict[str, str] = {}
    for key, value in config.items():
        env_key = f"{prefix}__{str(key).upper()}"
        if key == "event_listener" and isinstance(value, dict):
            env[env_key] = json.dumps(value)
            continue
        if isinstance(value, dict):
            env.update(ocean_config_env(value, env_key))
            continue
        if isinstance(value, bool):
            env[env_key] = "true" if value else "false"
        else:
            env[env_key] = str(value)
    return env
