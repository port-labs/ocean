from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.integration_validation.runner.integration.process import (
    IntegrationRunResult,
    run_ocean_sail_once,
)
from tools.integration_validation.runner.core.statuses import ScenarioIntegrationStatus


@pytest.mark.parametrize(
    ("returncode", "timed_out", "expected"),
    [
        (0, False, ScenarioIntegrationStatus.COMPLETED),
        (1, False, ScenarioIntegrationStatus.FAILED),
        (-1, True, ScenarioIntegrationStatus.TIMEOUT),
    ],
)
def test_integration_status(
    returncode: int,
    timed_out: bool,
    expected: ScenarioIntegrationStatus,
) -> None:
    result = IntegrationRunResult(
        returncode=returncode, stdout="", stderr="", timed_out=timed_out
    )
    assert result.integration_status() is expected


def test_run_ocean_sail_once_invokes_subprocess_with_integration_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration_root = tmp_path / "integration"
    integration_root.mkdir()

    captured: dict[str, Any] = {}

    class FakeCompletedProcess:
        returncode = 0
        stdout = b"ok"
        stderr = b""

    def fake_run(*args: Any, **kwargs: Any) -> FakeCompletedProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeCompletedProcess()

    monkeypatch.setenv("OCEAN_CLI", "/fake/ocean")
    monkeypatch.setattr(
        "tools.integration_validation.runner.integration.process.subprocess.run",
        fake_run,
    )

    result = run_ocean_sail_once(
        integration_root,
        integration_identifier="validate-sample-happy",
        integration_config={"exampleBaseUrl": "{{mock_base_url}}"},
        mock_base_url="http://127.0.0.1:9000",
    )

    assert result == IntegrationRunResult(
        returncode=0, stdout="ok", stderr="", timed_out=False
    )
    assert captured["args"][0] == ["/fake/ocean", "sail", "-O"]
    assert captured["kwargs"]["cwd"] == integration_root
    assert (
        captured["kwargs"]["env"]["OCEAN__INTEGRATION__CONFIG__EXAMPLE_BASE_URL"]
        == "http://127.0.0.1:9000"
    )
