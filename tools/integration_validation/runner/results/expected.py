"""Read and write ``expected/<scenario>/<blueprint>.json`` snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.integration_validation.runner.core.errors import ValidationSetupError
from tools.integration_validation.runner.core.models import (
    ScenarioDefinition,
    ValidationPaths,
)

EXPECTED_DIRNAME = "expected"
SNAPSHOT_SUFFIX = ".json"


def resolve_expected_dir(
    paths: ValidationPaths, scenario_name: str, scenario: ScenarioDefinition
) -> Path:
    """``expect.entities`` relative to ``validation/``, else ``expected/<scenario>/``."""
    configured = scenario.expect.entities if scenario.expect else None
    if configured is None:
        return paths.validation_root / EXPECTED_DIRNAME / scenario_name
    return paths.validation_root / configured


def load_expected(expected_dir: Path) -> dict[str, list[dict[str, Any]]] | None:
    """Snapshots keyed by blueprint, or ``None`` when the scenario has none yet.

    A blueprint without a file is expected to have no entities.
    """
    if not expected_dir.is_dir():
        return None
    files = sorted(expected_dir.glob(f"*{SNAPSHOT_SUFFIX}"))
    if not files:
        return None
    return {file.stem: _load_snapshot(file) for file in files}


def write_expected(
    expected_dir: Path, entities: dict[str, list[dict[str, Any]]]
) -> None:
    """Replace the scenario's snapshots with ``entities`` (already normalized).

    Blueprints without entities get no file, and files of blueprints that are
    now empty are removed, so the folder only ever describes this result.
    """
    try:
        expected_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for blueprint, blueprint_entities in sorted(entities.items()):
            if not blueprint_entities:
                continue
            file = expected_dir / f"{blueprint}{SNAPSHOT_SUFFIX}"
            file.write_text(dump_snapshot(blueprint_entities), encoding="utf-8")
            written.append(file)
        for stale in expected_dir.glob(f"*{SNAPSHOT_SUFFIX}"):
            if stale not in written:
                stale.unlink()
    except OSError as exc:
        raise ValidationSetupError(
            f"Could not write expected entities to {expected_dir}: {exc}"
        ) from exc


def dump_snapshot(entities: list[dict[str, Any]]) -> str:
    return json.dumps(entities, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_snapshot(file: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationSetupError(
            f"Could not load expected entities from {file}: {exc}"
        ) from exc

    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValidationSetupError(f"{file} must be a JSON array of entity objects")
    return raw
