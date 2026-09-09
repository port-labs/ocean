from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from port_ocean.core.probe import ProbeContext


def http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.atlassian.net/rest/api/3/myself")
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=httpx.Response(status_code, request=request),
    )


def _mock_client(**kwargs: Any) -> SimpleNamespace:
    defaults: dict[str, Any] = {
        "verify_current_user": AsyncMock(),
        "get_current_user_permissions": AsyncMock(return_value={}),
        "verify_teams_access": AsyncMock(),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class MockJiraProbe:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self.client = _mock_client()
        self._patch_client()

    def _patch_client(self) -> None:
        self._monkeypatch.setattr(
            "jira.probe.probe.get_or_create_jira_client",
            lambda: self.client,
        )

    def configure_client(self, **kwargs: Any) -> SimpleNamespace:
        self.client = _mock_client(**kwargs)
        self._patch_client()
        return self.client

    def configure_ocean(self, integration_config: dict[str, Any] | None = None) -> None:
        mock_ocean = MagicMock()
        mock_ocean.integration_config = integration_config or {}
        self._monkeypatch.setattr("jira.probe.probe.ocean", mock_ocean)


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context


@pytest.fixture
def mock_jira_probe(monkeypatch: pytest.MonkeyPatch) -> MockJiraProbe:
    return MockJiraProbe(monkeypatch)
