from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.models import (
    ScenarioDefinition,
    ScenariosDefaults,
    ScenariosDocument,
    ValidationPaths,
)


def resolve_validation_paths(integration_path: Path) -> ValidationPaths:
    integration_root = integration_path.resolve()
    validation_root = integration_root / "validation"
    return ValidationPaths(
        integration_root=integration_root,
        validation_root=validation_root,
        scenarios_file=validation_root / "scenarios.yaml",
        mock_root=validation_root / "mock",
    )


def load_scenarios_document(scenarios_file: Path) -> ScenariosDocument:
    if not scenarios_file.is_file():
        raise ValidationSetupError(
            f"Missing scenarios file: {scenarios_file}. "
            "Expected <integration>/validation/scenarios.yaml."
        )

    try:
        raw_text = scenarios_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationSetupError(f"Could not read {scenarios_file}: {exc}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ValidationSetupError(f"Malformed scenarios.yaml: {exc}") from exc

    if raw is None:
        raise ValidationSetupError(f"{scenarios_file} is empty")

    if not isinstance(raw, dict):
        raise ValidationSetupError(
            f"{scenarios_file} must be a mapping, got {type(raw).__name__}"
        )

    try:
        return ScenariosDocument.model_validate(raw)
    except ValidationError as exc:
        raise ValidationSetupError(
            _format_pydantic_error(f"{scenarios_file}", exc)
        ) from exc


def resolve_integration_resource_path(
    validation_paths: ValidationPaths, relative_path: str, resource_label: str
) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        if candidate.is_file():
            return candidate
        raise ValidationSetupError(f"{resource_label} not found: {relative_path}")
    integration_relative = validation_paths.integration_root / candidate
    if integration_relative.is_file():
        return integration_relative
    raise ValidationSetupError(
        f"{resource_label} not found: {relative_path} "
        f"(looked under {validation_paths.integration_root})"
    )


def resolve_scenario_blueprints_path(
    validation_paths: ValidationPaths,
    defaults: ScenariosDefaults,
    scenario: ScenarioDefinition,
) -> Path:
    relative = (
        scenario.blueprints if scenario.blueprints is not None else defaults.blueprints
    )
    return resolve_integration_resource_path(validation_paths, relative, "blueprints")


def _format_pydantic_error(prefix: str, exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", ()))
        msg = error.get("msg", "validation error")
        if loc:
            parts.append(f"{prefix}: {loc}: {msg}")
        else:
            parts.append(f"{prefix}: {msg}")
    return ";\n".join(parts) if parts else f"{prefix}: invalid configuration"
