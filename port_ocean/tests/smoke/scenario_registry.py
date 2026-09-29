from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
SMOKE_DIR = Path(__file__).parent
REPO_ROOT = SMOKE_DIR.parents[2]
Lifecycle = Literal["once", "daemon"]


@dataclass(frozen=True)
class SmokeScenario:
    name: str
    lifecycle: Lifecycle
    suffix: str
    resource_kinds: tuple[str, ...]
    host_port: int
    tests: tuple[str, ...]
    wait_for_resync: bool
    ocean: dict[str, Any]


def list_scenario_names() -> list[str]:
    return sorted(path.stem for path in SCENARIOS_DIR.glob("*.yaml"))


def load_scenario(name: str) -> SmokeScenario:
    path = SCENARIOS_DIR / f"{name}.yaml"
    if not path.is_file():
        available = ", ".join(list_scenario_names()) or "(none)"
        raise ValueError(f"Unknown smoke scenario '{name}'. Available: {available}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid smoke scenario '{name}': expected a mapping")
    return _parse_scenario(name, raw)


def ocean_config_env(config: dict[str, Any], prefix: str = "OCEAN") -> dict[str, str]:
    """Flatten scenario Ocean config into ``OCEAN__*`` environment variables.

    ``event_listener`` is emitted as one JSON value because it is a union
    selected by ``type``. Other nested mappings use the ``__`` delimiter.
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
        env[env_key] = _env_value(value)
    return env


def _parse_scenario(name: str, raw: dict[str, Any]) -> SmokeScenario:
    lifecycle = raw.get("lifecycle", "daemon")
    if lifecycle not in {"once", "daemon"}:
        raise ValueError(
            f"Invalid smoke scenario '{name}': lifecycle must be 'once' or 'daemon'"
        )

    tests_raw = raw.get("tests", [])
    if not isinstance(tests_raw, list) or not all(
        isinstance(item, str) for item in tests_raw
    ):
        raise ValueError(
            f"Invalid smoke scenario '{name}': tests must be a list of paths"
        )

    ocean = raw.get("ocean", {})
    if not isinstance(ocean, dict):
        raise ValueError(f"Invalid smoke scenario '{name}': ocean must be a mapping")

    kinds = raw.get("resource_kinds", ["fake-department", "fake-person"])
    if not isinstance(kinds, list) or not all(isinstance(kind, str) for kind in kinds):
        raise ValueError(
            f"Invalid smoke scenario '{name}': resource_kinds must be a list of strings"
        )

    return SmokeScenario(
        name=name,
        lifecycle=lifecycle,
        suffix=str(raw.get("suffix", name)),
        resource_kinds=tuple(kinds),
        host_port=int(raw.get("host_port", 18080)),
        tests=tuple(_resolve_test(name, test) for test in tests_raw),
        wait_for_resync=bool(raw.get("wait_for_resync", False)),
        ocean=ocean,
    )


def _resolve_test(scenario: str, test: str) -> str:
    candidate = Path(test)
    if candidate.is_absolute():
        resolved = candidate
    elif test.startswith("port_ocean/"):
        resolved = REPO_ROOT / test
    else:
        resolved = SMOKE_DIR / test
    if not resolved.is_file():
        raise ValueError(
            f"Invalid smoke scenario '{scenario}': test file not found: {test}"
        )
    return str(resolved.relative_to(REPO_ROOT))


def _env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
