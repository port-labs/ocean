"""Tests for :func:`azure_devops.webhooks.setup.setup_webhooks_for_all_orgs`.

Covered behavior:
- Early return when the event listener type is ``ONCE``
- Early return when ``ocean.app.base_url`` is unset
- Single-org: ``create_webhook_subscriptions`` is called once, and
  any exception propagates unchanged (BC guarantee)
- Single-org with ``is_projects_limited=True``: subscriptions are
  created per project
- Multi-org: ``create_webhook_subscriptions`` is called once per
  configured organization
- Multi-org error isolation: if one org raises, the remaining orgs
  still get their webhooks set up and the error is logged
"""

from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.ocean import ocean

from azure_devops.client.auth import PersonalAccessTokenAuthenticator
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.webhooks.setup import setup_webhooks_for_all_orgs


@pytest.fixture
def mock_base_url(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Ensure ocean.app.base_url is a valid URL string for the test."""
    monkeypatch.setattr(ocean.app, "base_url", "https://port.example/webhook")
    yield "https://port.example/webhook"


@pytest.fixture
def non_once_event_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Force the event listener type to something other than ONCE so
    setup_webhooks_for_all_orgs proceeds past its early-return guard."""
    monkeypatch.setattr(
        "port_ocean.context.ocean.PortOceanContext.event_listener_type",
        "POLLING",
    )
    yield


def _make_client(org_url: str) -> AzureDevopsClient:
    """Build a real AzureDevopsClient instance bound to ``org_url``
    with its ``create_webhook_subscriptions`` method mocked out."""
    client = AzureDevopsClient(org_url, PersonalAccessTokenAuthenticator("pat"), "port")
    client.create_webhook_subscriptions = AsyncMock()  # type: ignore[method-assign]
    return client


def _install_manager(
    monkeypatch: pytest.MonkeyPatch,
    clients: list[tuple[str, AzureDevopsClient]],
) -> None:
    """Patch AzureDevopsClientManager.create_from_ocean_config_no_cache
    (as seen from inside azure_devops.webhooks.setup) to return a
    manager exposing the given list of clients."""
    manager = MagicMock(spec=AzureDevopsClientManager)
    manager.get_clients.return_value = clients
    monkeypatch.setattr(
        "azure_devops.webhooks.setup.AzureDevopsClientManager.create_from_ocean_config_no_cache",
        classmethod(lambda cls: manager),
    )


# ---- Early-return guards ----


@pytest.mark.asyncio
async def test_once_event_listener_skips_webhook_setup(
    monkeypatch: pytest.MonkeyPatch,
    mock_base_url: str,
) -> None:
    monkeypatch.setattr(
        "port_ocean.context.ocean.PortOceanContext.event_listener_type",
        "ONCE",
    )
    # If the manager were consulted, this test would crash because the
    # classmethod isn't patched. The early-return ensures it isn't.
    await setup_webhooks_for_all_orgs()


@pytest.mark.asyncio
async def test_missing_base_url_skips_webhook_setup(
    monkeypatch: pytest.MonkeyPatch,
    non_once_event_listener: None,
) -> None:
    monkeypatch.setattr(ocean.app, "base_url", None)
    await setup_webhooks_for_all_orgs()


# ---- Single-org ----


@pytest.mark.asyncio
async def test_single_org_setup_calls_create_subscriptions_once(
    monkeypatch: pytest.MonkeyPatch,
    mock_base_url: str,
    non_once_event_listener: None,
) -> None:
    client = _make_client("https://dev.azure.com/single-org")
    _install_manager(monkeypatch, [("https://dev.azure.com/single-org", client)])

    await setup_webhooks_for_all_orgs()

    client.create_webhook_subscriptions.assert_awaited_once_with(  # type: ignore[attr-defined]
        mock_base_url, webhook_secret="test-secret"
    )


@pytest.mark.asyncio
async def test_single_org_setup_propagates_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    mock_base_url: str,
    non_once_event_listener: None,
) -> None:
    """BC guarantee: in single-org mode, failures in
    ``create_webhook_subscriptions`` must propagate exactly as they did
    before multi-org support existed."""
    client = _make_client("https://dev.azure.com/broken-org")
    client.create_webhook_subscriptions.side_effect = RuntimeError("boom")  # type: ignore[attr-defined]
    _install_manager(monkeypatch, [("https://dev.azure.com/broken-org", client)])

    with pytest.raises(RuntimeError, match="boom"):
        await setup_webhooks_for_all_orgs()


@pytest.mark.asyncio
async def test_single_org_projects_limited_creates_per_project(
    monkeypatch: pytest.MonkeyPatch,
    mock_base_url: str,
    non_once_event_listener: None,
) -> None:
    ocean.integration_config["is_projects_limited"] = True
    try:

        async def _fake_generate_projects(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {"id": "proj-1", "name": "Proj One"},
                {"id": "proj-2", "name": "Proj Two"},
            ]

        client = _make_client("https://dev.azure.com/limited-org")
        client.generate_projects = _fake_generate_projects  # type: ignore[method-assign]
        _install_manager(monkeypatch, [("https://dev.azure.com/limited-org", client)])

        await setup_webhooks_for_all_orgs()

        assert client.create_webhook_subscriptions.await_count == 2  # type: ignore[attr-defined]
        client.create_webhook_subscriptions.assert_any_await(  # type: ignore[attr-defined]
            mock_base_url, "proj-1", "test-secret"
        )
        client.create_webhook_subscriptions.assert_any_await(  # type: ignore[attr-defined]
            mock_base_url, "proj-2", "test-secret"
        )
    finally:
        ocean.integration_config["is_projects_limited"] = False


# ---- Multi-org ----


@pytest.mark.asyncio
async def test_multi_org_setup_calls_create_subscriptions_per_org(
    monkeypatch: pytest.MonkeyPatch,
    mock_base_url: str,
    non_once_event_listener: None,
) -> None:
    client_alpha = _make_client("https://dev.azure.com/org-alpha")
    client_beta = _make_client("https://dev.azure.com/org-beta")
    _install_manager(
        monkeypatch,
        [
            ("https://dev.azure.com/org-alpha", client_alpha),
            ("https://dev.azure.com/org-beta", client_beta),
        ],
    )

    await setup_webhooks_for_all_orgs()

    client_alpha.create_webhook_subscriptions.assert_awaited_once_with(  # type: ignore[attr-defined]
        mock_base_url, webhook_secret="test-secret"
    )
    client_beta.create_webhook_subscriptions.assert_awaited_once_with(  # type: ignore[attr-defined]
        mock_base_url, webhook_secret="test-secret"
    )


@pytest.mark.asyncio
async def test_multi_org_setup_isolates_failing_org(
    monkeypatch: pytest.MonkeyPatch,
    mock_base_url: str,
    non_once_event_listener: None,
) -> None:
    """Multi-org: one org's failure must not abort webhook setup for
    the other orgs. The error should be logged but swallowed."""
    client_good = _make_client("https://dev.azure.com/org-good")
    client_bad = _make_client("https://dev.azure.com/org-bad")
    client_bad.create_webhook_subscriptions.side_effect = RuntimeError(  # type: ignore[attr-defined]
        "org-bad pat is expired"
    )
    _install_manager(
        monkeypatch,
        [
            ("https://dev.azure.com/org-bad", client_bad),
            ("https://dev.azure.com/org-good", client_good),
        ],
    )

    # Should NOT raise — the bad org's exception is caught and logged.
    await setup_webhooks_for_all_orgs()

    # Good org still got its webhook set up.
    client_good.create_webhook_subscriptions.assert_awaited_once()  # type: ignore[attr-defined]
    client_bad.create_webhook_subscriptions.assert_awaited_once()  # type: ignore[attr-defined]
