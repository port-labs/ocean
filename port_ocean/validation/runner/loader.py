from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from port_ocean.validation.runner.errors import ValidationSetupError
from port_ocean.validation.runner.models import ScenariosDocument, ValidationPaths


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
        raise ValidationSetupError("scenarios.yaml is empty")

    if not isinstance(raw, dict):
        raise ValidationSetupError(
            f"scenarios.yaml must be a mapping, got {type(raw).__name__}"
        )

    try:
        return ScenariosDocument.model_validate(raw)
    except ValidationError as exc:
        raise ValidationSetupError(
            _format_pydantic_error("scenarios.yaml", exc)
        ) from exc


def resolve_port_app_config_path(
    validation_paths: ValidationPaths, defaults_port_app_config: str
) -> Path:
    candidate = Path(defaults_port_app_config)
    if candidate.is_absolute():
        return candidate
    integration_relative = validation_paths.integration_root / candidate
    if integration_relative.is_file():
        return integration_relative
    raise ValidationSetupError(
        f"port_app_config not found: {defaults_port_app_config} "
        f"(looked under {validation_paths.integration_root})"
    )


def _format_pydantic_error(prefix: str, exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", ()))
        msg = error.get("msg", "validation error")
        if loc:
            parts.append(f"{prefix}: {loc}: {msg}")
        else:
            parts.append(f"{prefix}: {msg}")
    return "; ".join(parts) if parts else f"{prefix}: invalid configuration"
