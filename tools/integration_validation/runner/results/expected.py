"""Read and write ``expected/<scenario>/<blueprint>.json`` snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from tools.integration_validation.runner.core.errors import ValidationSetupError
from tools.integration_validation.runner.core.models import (
    EntitiesByBlueprint,
    PortEntity,
    ScenarioDefinition,
    ValidationPaths,
)

EXPECTED_DIRNAME = "expected"
SNAPSHOT_SUFFIX = ".json"
SNAPSHOT_ADAPTER = TypeAdapter(list[PortEntity])


def resolve_expected_dir(
    paths: ValidationPaths, scenario_name: str, scenario: ScenarioDefinition
) -> Path:
    """``expect.entities`` relative to ``validation/``, else ``expected/<scenario>/``."""
    configured = scenario.expect.entities if scenario.expect else None
    if configured is None:
        return paths.validation_root / EXPECTED_DIRNAME / scenario_name
    return paths.validation_root / configured


def load_expected(expected_dir: Path) -> EntitiesByBlueprint | None:
    """Snapshots keyed by blueprint, or ``None`` when the scenario has none yet.

    "None yet" means no snapshot file at all; ``write_expected`` always leaves
    one per blueprint. A blueprint without a file (for example one added to the
    blueprints file later) is expected to have no entities.
    """
    files = sorted(expected_dir.glob(f"*{SNAPSHOT_SUFFIX}"))
    if not files:
        return None
    return {file.stem: _load_snapshot(file) for file in files}


def write_expected(expected_dir: Path, entities: EntitiesByBlueprint) -> None:
    """Replace the scenario's snapshots with ``entities`` (already normalized).

    Every blueprint gets a file, ``[]`` when it has no entities, so an empty
    result is still an expectation: ``load_expected`` treats a folder without
    files as a first run. Files of blueprints no longer in ``entities`` are
    removed.
    """
    try:
        expected_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for blueprint, blueprint_entities in sorted(entities.items()):
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


def dump_snapshot(entities: list[PortEntity]) -> str:
    payload = [entity.model_dump(exclude_unset=True) for entity in entities]
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_snapshot(file: Path) -> list[PortEntity]:
    try:
        content = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationSetupError(
            f"Could not load expected entities from {file}: {exc}"
        ) from exc
    try:
        return SNAPSHOT_ADAPTER.validate_json(content)
    except ValidationError as exc:
        raise ValidationSetupError(
            f"Could not load expected entities from {file}: it must be a JSON "
            f"array of entity objects with an identifier. {exc}"
        ) from exc
