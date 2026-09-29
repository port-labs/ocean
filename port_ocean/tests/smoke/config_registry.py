from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

CONFIGS_DIR = Path(__file__).parent / "configs"
Lifecycle = Literal["once", "daemon"]


@dataclass(frozen=True)
class SmokeConfig:
    name: str
    wait_for_resync: bool
    ocean: dict[str, Any]

    @property
    def lifecycle(self) -> Lifecycle:
        listener = self.ocean.get("event_listener") or {}
        if (
            isinstance(listener, dict)
            and str(listener.get("type", "")).upper() == "ONCE"
        ):
            return "once"
        return "daemon"


def list_config_names() -> list[str]:
    return sorted(path.stem for path in CONFIGS_DIR.glob("*.yaml"))


def load_config(name: str) -> SmokeConfig:
    path = CONFIGS_DIR / f"{name}.yaml"
    if not path.is_file():
        available = ", ".join(list_config_names()) or "(none)"
        raise ValueError(f"Unknown smoke config '{name}'. Available: {available}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid smoke config '{name}': expected a mapping")
    ocean = raw.get("ocean", {})
    if not isinstance(ocean, dict):
        raise ValueError(f"Invalid smoke config '{name}': ocean must be a mapping")
    return SmokeConfig(
        name=name,
        wait_for_resync=bool(raw.get("wait_for_resync", False)),
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
