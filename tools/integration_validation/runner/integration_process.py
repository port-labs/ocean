from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.integration_config_env import (
    build_sail_subprocess_env,
)

DEFAULT_MOCK_BASE_URL = "http://127.0.0.1:9000"
DEFAULT_INTEGRATION_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class IntegrationRunResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def resolve_ocean_sail_command() -> list[str]:
    ocean = os.environ.get("OCEAN_CLI") or shutil.which("ocean")
    if not ocean:
        raise ValidationSetupError(
            "Could not find the ocean CLI on PATH. Run `poetry install` from the "
            "repo root or set OCEAN_CLI to the ocean executable."
        )
    return [ocean, "sail", "-O"]


def run_ocean_sail_once(
    integration_root: Path,
    *,
    integration_identifier: str,
    integration_config: dict[str, object],
    mock_base_url: str,
    timeout_seconds: float = DEFAULT_INTEGRATION_TIMEOUT_SECONDS,
) -> IntegrationRunResult:
    """Run ``ocean sail -O`` against the integration directory.

    The mock server must already be listening at ``mock_base_url`` with the
    scenario loaded; this module does not start it.
    """
    command = resolve_ocean_sail_command()
    env = build_sail_subprocess_env(
        integration_identifier=integration_identifier,
        integration_config=integration_config,
        mock_base_url=mock_base_url,
    )
    logger.info(
        f"Starting integration subprocess ({' '.join(command)}) "
        f"for {integration_identifier}"
    )

    try:
        completed = subprocess.run(
            command,
            cwd=integration_root,
            env=env,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            f"Integration subprocess timed out after {timeout_seconds}s "
            f"({integration_identifier})"
        )
        return IntegrationRunResult(
            returncode=-1,
            stdout=_decode_bytes(exc.stdout),
            stderr=_decode_bytes(exc.stderr),
            timed_out=True,
        )

    return IntegrationRunResult(
        returncode=completed.returncode,
        stdout=_decode_bytes(completed.stdout),
        stderr=_decode_bytes(completed.stderr),
        timed_out=False,
    )


def _decode_bytes(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode(errors="replace")
