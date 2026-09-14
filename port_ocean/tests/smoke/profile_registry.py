from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

PROFILES_DIR = Path(__file__).parent / "profiles"
ProfileMode = Literal["once", "polling"]


@dataclass(frozen=True)
class SmokeProfile:
    name: str
    mode: ProfileMode
    profile_suffix: str
    resource_kinds: tuple[str, ...]
    host_port: int
    integration_config: dict[str, Any]


def _parse_profile(name: str, raw: dict[str, Any]) -> SmokeProfile:
    mode = raw.get("mode", "once")
    if mode not in {"once", "polling"}:
        raise ValueError(
            f"Invalid smoke profile '{name}': mode must be 'once' or 'polling'"
        )
    return SmokeProfile(
        name=name,
        mode=mode,
        profile_suffix=str(raw.get("profile_suffix", name)),
        resource_kinds=tuple(
            raw.get("resource_kinds", ("fake-department", "fake-person"))
        ),
        host_port=int(raw.get("host_port", 18080)),
        integration_config=dict(raw.get("integration", {})),
    )


def list_profile_names() -> list[str]:
    return sorted(path.stem for path in PROFILES_DIR.glob("*.yaml"))


def load_profile(name: str) -> SmokeProfile:
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.is_file():
        available = ", ".join(list_profile_names()) or "(none)"
        raise ValueError(f"Unknown smoke profile '{name}'. Available: {available}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid smoke profile '{name}': expected a mapping")
    return _parse_profile(name, raw)


def integration_config_env_key(key: str) -> str:
    return f"OCEAN__INTEGRATION__CONFIG__{key.upper()}"
