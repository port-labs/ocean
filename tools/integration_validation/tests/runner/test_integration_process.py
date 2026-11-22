from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.integration_validation.runner.integration_process import (
    IntegrationRunResult,
    run_ocean_sail_once,
)


@pytest.mark.asyncio
async def test_run_ocean_sail_once_invokes_subprocess_with_integration_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration_root = tmp_path / "integration"
    integration_root.mkdir()

    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"ok", b""

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setenv("OCEAN_CLI", "/fake/ocean")
    monkeypatch.setattr(
        "tools.integration_validation.runner.integration_process.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    result = await run_ocean_sail_once(
        integration_root,
        integration_identifier="validate-sample-happy",
        integration_config={"exampleBaseUrl": "{{mock_base_url}}"},
        mock_base_url="http://127.0.0.1:9000",
    )

    assert result == IntegrationRunResult(
        returncode=0, stdout="ok", stderr="", timed_out=False
    )
    assert captured["args"] == ("/fake/ocean", "sail", "-O")
    assert captured["kwargs"]["cwd"] == integration_root
    assert (
        captured["kwargs"]["env"]["OCEAN__INTEGRATION__CONFIG__EXAMPLE_BASE_URL"]
        == "http://127.0.0.1:9000"
    )
