from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from pydantic import ValidationError

from port_ocean.config.settings import PortSettings
from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.loader import resolve_port_app_config_path
from tools.integration_validation.runner.models import (
    ScenariosDocument,
    ValidationPaths,
)

_PORT_CREDENTIAL_HINT = (
    "Set OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET, and "
    "OCEAN__PORT__BASE_URL in the environment or integrations/<name>/.env."
)


def run_preflight(
    validation_paths: ValidationPaths,
    scenarios: ScenariosDocument,
    selected_scenarios: list[str] | None,
) -> None:
    _ensure_validation_directory(validation_paths)
    _load_port_credentials(validation_paths.integration_root)
    resolve_port_app_config_path(validation_paths, scenarios.defaults.port_app_config)
    _selected_scenario_names(scenarios, selected_scenarios)


def _ensure_validation_directory(validation_paths: ValidationPaths) -> None:
    if not validation_paths.validation_root.is_dir():
        raise ValidationSetupError(
            f"Validation folder not found: {validation_paths.validation_root}. "
            "Expected <integration>/validation/."
        )
    if not validation_paths.mock_root.is_dir():
        raise ValidationSetupError(
            f"Mock fixture root not found: {validation_paths.mock_root}. "
            "Expected <integration>/validation/mock/ (mock server --fixture-root)."
        )


def _load_port_credentials(integration_root: Path) -> None:
    env_file = integration_root / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)

    missing: list[str] = []
    if not os.environ.get("OCEAN__PORT__CLIENT_ID"):
        missing.append("OCEAN__PORT__CLIENT_ID")
    if not os.environ.get("OCEAN__PORT__CLIENT_SECRET"):
        missing.append("OCEAN__PORT__CLIENT_SECRET")
    if not os.environ.get("OCEAN__PORT__BASE_URL"):
        missing.append("OCEAN__PORT__BASE_URL")

    if missing:
        raise ValidationSetupError(
            f"Missing Port credentials ({', '.join(missing)}). {_PORT_CREDENTIAL_HINT}"
        )

    try:
        PortSettings(
            client_id=os.environ["OCEAN__PORT__CLIENT_ID"],
            client_secret=os.environ["OCEAN__PORT__CLIENT_SECRET"],
            base_url=os.environ["OCEAN__PORT__BASE_URL"],
        )
    except (KeyError, ValidationError) as exc:
        raise ValidationSetupError(
            f"Invalid Port credentials in environment: {exc}. {_PORT_CREDENTIAL_HINT}"
        ) from exc


def _selected_scenario_names(
    scenarios: ScenariosDocument, selected_scenarios: list[str] | None
) -> list[str]:
    if not selected_scenarios:
        return list(scenarios.scenarios.keys())

    unknown = [name for name in selected_scenarios if name not in scenarios.scenarios]
    if unknown:
        raise ValidationSetupError(
            f"Unknown scenario(s): {', '.join(unknown)}. "
            f"Available: {', '.join(sorted(scenarios.scenarios))}"
        )
    return selected_scenarios
