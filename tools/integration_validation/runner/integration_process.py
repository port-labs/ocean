from __future__ import annotations

import asyncio
import os
import shutil
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from loguru import logger

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.integration_config_env import (
    build_sail_subprocess_env,
)

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


@asynccontextmanager
async def _ocean_sail_subprocess(
    integration_root: Path,
    env: dict[str, str],
) -> AsyncIterator[asyncio.subprocess.Process]:
    command = resolve_ocean_sail_command()
    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=integration_root,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield proc
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def _read_subprocess_output(
    proc: asyncio.subprocess.Process,
    *,
    timeout_seconds: float,
    integration_identifier: str,
) -> tuple[str, str, int, bool]:
    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        timed_out = True
        stdout_bytes, stderr_bytes = b"", b""
        logger.error(
            f"Integration subprocess timed out after {timeout_seconds}s "
            f"({integration_identifier})"
        )

    stdout = (stdout_bytes or b"").decode(errors="replace")
    stderr = (stderr_bytes or b"").decode(errors="replace")
    returncode = proc.returncode if proc.returncode is not None else -1
    return stdout, stderr, returncode, timed_out


async def run_ocean_sail_once(
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
    env = build_sail_subprocess_env(
        integration_identifier=integration_identifier,
        integration_config=integration_config,
        mock_base_url=mock_base_url,
    )
    logger.info(
        f"Starting integration subprocess ({' '.join(resolve_ocean_sail_command())}) "
        f"for {integration_identifier}"
    )

    async with _ocean_sail_subprocess(integration_root, env) as proc:
        stdout, stderr, returncode, timed_out = await _read_subprocess_output(
            proc,
            timeout_seconds=timeout_seconds,
            integration_identifier=integration_identifier,
        )

    return IntegrationRunResult(
        returncode=returncode if not timed_out else -1,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
    )
