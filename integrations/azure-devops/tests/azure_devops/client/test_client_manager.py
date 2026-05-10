from typing import Any, Generator

import pytest

from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import ocean

from azure_devops.client.auth import (
    PersonalAccessTokenAuthenticator,
    ServicePrincipalAuthenticator,
)
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import (
    CLIENT_MANAGER_CACHE_KEY,
    AzureDevopsClientManager,
)

_SP_KEYS = ("organization_urls", "client_id", "client_secret", "tenant_id")
_LEGACY_KEYS = ("organization_url", "personal_access_token")


@pytest.fixture
def event_context() -> Generator[None, None, None]:
    """Push a fresh EventContext so manager caching can write to
    event.attributes without polluting other tests."""
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


def _snapshot_config() -> dict[str, Any]:
    return {key: ocean.integration_config.get(key) for key in _LEGACY_KEYS + _SP_KEYS}


def _restore_config(snapshot: dict[str, Any]) -> None:
    for key, value in snapshot.items():
        ocean.integration_config[key] = value


@pytest.fixture
def set_legacy_single_org() -> Generator[None, None, None]:
    """Configure ocean.integration_config for legacy single-org mode."""
    previous = _snapshot_config()
    ocean.integration_config["organization_url"] = "https://dev.azure.com/legacy-org"
    ocean.integration_config["personal_access_token"] = "legacy-pat"
    for key in _SP_KEYS:
        ocean.integration_config[key] = None
    yield
    _restore_config(previous)


@pytest.fixture
def set_service_principal_multi_org() -> Generator[list[str], None, None]:
    """Configure ocean.integration_config for Service Principal multi-org mode."""
    previous = _snapshot_config()
    urls = [
        "https://dev.azure.com/org-one",
        "https://dev.azure.com/org-two",
    ]
    for key in _LEGACY_KEYS:
        ocean.integration_config[key] = None
    ocean.integration_config["organization_urls"] = urls
    ocean.integration_config["client_id"] = "sp-client-id"
    ocean.integration_config["client_secret"] = "sp-client-secret"
    ocean.integration_config["tenant_id"] = "sp-tenant-id"
    yield urls
    _restore_config(previous)


def test_legacy_single_org_builds_one_client(
    set_legacy_single_org: None, event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    clients = manager.get_clients()
    assert len(clients) == 1
    assert manager.is_multi_org is False
    org_url, client = clients[0]
    assert org_url == "https://dev.azure.com/legacy-org"
    assert isinstance(client, AzureDevopsClient)
    assert isinstance(client._authenticator, PersonalAccessTokenAuthenticator)


def test_legacy_single_org_client_lookup(
    set_legacy_single_org: None, event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    client = manager.get_client_for_org("https://dev.azure.com/legacy-org")
    assert client is not None
    assert isinstance(client, AzureDevopsClient)


def test_service_principal_builds_one_client_per_url(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    clients = manager.get_clients()
    assert len(clients) == len(set_service_principal_multi_org)
    assert manager.is_multi_org is True
    urls = {url for url, _ in clients}
    assert urls == set(set_service_principal_multi_org)


def test_service_principal_clients_share_one_authenticator(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    """Critical: the Entra ID token is tenant-scoped, so all clients must
    share the same authenticator instance and therefore the same cached token."""
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    clients = manager.get_clients()
    authenticators = {id(client._authenticator) for _, client in clients}
    assert len(authenticators) == 1
    sample_auth = clients[0][1]._authenticator
    assert isinstance(sample_auth, ServicePrincipalAuthenticator)


def test_service_principal_client_lookup_by_exact_url(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    client = manager.get_client_for_org("https://dev.azure.com/org-one")
    assert client is not None


def test_service_principal_lookup_normalizes_trailing_slash(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    client = manager.get_client_for_org("https://dev.azure.com/org-one/")
    assert client is not None


def test_service_principal_lookup_unknown_url_returns_none(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    assert manager.get_client_for_org("https://dev.azure.com/unknown-org") is None


def test_service_principal_with_trailing_slash_in_url_list(
    event_context: None,
) -> None:
    previous = _snapshot_config()
    for key in _LEGACY_KEYS:
        ocean.integration_config[key] = None
    ocean.integration_config["organization_urls"] = ["https://dev.azure.com/trailing/"]
    ocean.integration_config["client_id"] = "c"
    ocean.integration_config["client_secret"] = "s"
    ocean.integration_config["tenant_id"] = "t"
    try:
        manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
        assert manager.get_client_for_org("https://dev.azure.com/trailing") is not None
    finally:
        _restore_config(previous)


def test_create_from_ocean_config_caches_within_event(
    set_legacy_single_org: None, event_context: None
) -> None:
    first = AzureDevopsClientManager.create_from_ocean_config()
    second = AzureDevopsClientManager.create_from_ocean_config()
    assert first is second
    from port_ocean.context.event import event as active_event

    assert active_event.attributes.get(CLIENT_MANAGER_CACHE_KEY) is first


def test_create_from_ocean_config_no_cache_returns_fresh_instance(
    set_legacy_single_org: None, event_context: None
) -> None:
    first = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    second = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    assert first is not second


def test_bad_config_raises_at_build(event_context: None) -> None:
    previous = _snapshot_config()
    for key in _LEGACY_KEYS + _SP_KEYS:
        ocean.integration_config[key] = None
    try:
        with pytest.raises(ValueError, match="requires either"):
            AzureDevopsClientManager.create_from_ocean_config_no_cache()
    finally:
        _restore_config(previous)
