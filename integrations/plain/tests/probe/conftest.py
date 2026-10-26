from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from plain.exceptions import PlainGraphQLError, PlainHTTPError
from port_ocean.core.probe import ProbeContext


def plain_http_error(status_code: int) -> PlainHTTPError:
    return PlainHTTPError(status_code, f"HTTP {status_code}")


def plain_unauthenticated_error() -> PlainGraphQLError:
    return PlainGraphQLError(
        [
            {
                "message": "Not authenticated",
                "extensions": {"code": "UNAUTHENTICATED"},
            }
        ]
    )


def request_error() -> httpx.RequestError:
    return httpx.RequestError(
        "connection failed",
        request=httpx.Request("POST", "https://core-api.uk.plain.com/graphql/v1"),
    )


def _mock_client(**kwargs: Any) -> SimpleNamespace:
    defaults: dict[str, Any] = {
        "verify_authentication": AsyncMock(),
        "get_my_permissions": AsyncMock(return_value={}),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class MockPlainProbe:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self.client = _mock_client()
        self._patch_client()

    def _patch_client(self) -> None:
        self._monkeypatch.setattr(
            "plain.probe.probe.PlainClient",
            lambda: self.client,
        )

    def configure_client(self, **kwargs: Any) -> SimpleNamespace:
        self.client = _mock_client(**kwargs)
        self._patch_client()
        return self.client


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context


@pytest.fixture
def mock_plain_probe(monkeypatch: pytest.MonkeyPatch) -> MockPlainProbe:
    return MockPlainProbe(monkeypatch)
