from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from port_ocean.core.probe import ProbeContext

BASE_URL = "https://api.datadoghq.com"
APP_KEY = "app-key-ending-abcd"
USER_ID = "user-1"


def http_status_error(
    status_code: int, path: str = "/api/v2/current_user"
) -> Exception:
    request = httpx.Request("GET", f"{BASE_URL}{path}")
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=httpx.Response(status_code, request=request),
    )


def request_error() -> Exception:
    return httpx.ConnectError(
        "connection failed",
        request=httpx.Request("GET", f"{BASE_URL}/api/v2/current_user"),
    )


def application_key(last4: str, scopes: list[str] | None) -> dict[str, Any]:
    return {"attributes": {"last4": last4, "scopes": scopes}}


def make_client(**overrides: Any) -> SimpleNamespace:
    """A DatadogClient stand-in: valid keys, owner holds *role_permissions*,
    configured application key is unscoped."""
    role_permissions: set[str] = overrides.pop("role_permissions", set())
    defaults: dict[str, Any] = {
        "api_url": BASE_URL,
        "dd_app_key": APP_KEY,
        "access_token": None,
        "org_name": None,
        "org_id": None,
        "get_current_user": AsyncMock(return_value={"id": USER_ID}),
        "get_user_permissions": AsyncMock(return_value=role_permissions),
        "get_current_user_application_keys": AsyncMock(
            return_value=[application_key("abcd", None)]
        ),
        "validate_api_key": AsyncMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context


@pytest.fixture
def set_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., None]:
    def _set(clients: list[SimpleNamespace], *, multi_org: bool = False) -> None:
        manager = SimpleNamespace(is_multi_org=multi_org, clients=clients)
        monkeypatch.setattr("datadog.probe.probe.get_client_manager", lambda: manager)

    return _set
