from typing import Any, Generator

import pytest

from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import hash_func

from azure_devops.client.auth import PersonalAccessTokenAuthenticator
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager

_SP_KEYS = ("organization_urls", "client_id", "client_secret", "tenant_id")
_LEGACY_KEYS = ("organization_url", "personal_access_token")


@pytest.fixture
def event_context() -> Generator[None, None, None]:
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


@pytest.fixture
def set_service_principal_multi_org() -> Generator[list[str], None, None]:
    urls = [
        "https://dev.azure.com/org-alpha",
        "https://dev.azure.com/org-beta",
    ]
    previous: dict[str, Any] = {
        key: ocean.integration_config.get(key) for key in _LEGACY_KEYS + _SP_KEYS
    }
    for key in _LEGACY_KEYS:
        ocean.integration_config[key] = None
    ocean.integration_config["organization_urls"] = urls
    ocean.integration_config["client_id"] = "sp-client-id"
    ocean.integration_config["client_secret"] = "sp-client-secret"
    ocean.integration_config["tenant_id"] = "sp-tenant-id"
    yield urls
    for key, value in previous.items():
        ocean.integration_config[key] = value


def test_manager_returns_client_for_known_org(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    client = manager.get_client_for_org("https://dev.azure.com/org-alpha")
    assert isinstance(client, AzureDevopsClient)
    assert client._organization_base_url == "https://dev.azure.com/org-alpha"


def test_manager_normalizes_trailing_slash(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    client = manager.get_client_for_org("https://dev.azure.com/org-alpha/")
    assert client is not None
    assert client._organization_base_url == "https://dev.azure.com/org-alpha"


def test_manager_returns_none_for_unknown_org(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    assert manager.get_client_for_org("https://dev.azure.com/unknown-org") is None


def test_get_client_for_org_or_first_falls_back_on_unknown(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    client = manager.get_client_for_org_or_first("https://dev.azure.com/unknown-org")
    assert isinstance(client, AzureDevopsClient)
    assert client._organization_base_url in set_service_principal_multi_org


def test_get_client_for_org_or_first_with_none_returns_first(
    set_service_principal_multi_org: list[str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config()
    client = manager.get_client_for_org_or_first(None)
    assert isinstance(client, AzureDevopsClient)
    assert client._organization_base_url in set_service_principal_multi_org


def test_get_client_for_org_or_first_raises_when_empty() -> None:
    manager = AzureDevopsClientManager()
    with pytest.raises(ValueError, match="No Azure DevOps clients configured"):
        manager.get_client_for_org_or_first(None)


CACHED_BACKING_METHODS = [
    "_generate_projects_cached",
    "_generate_teams_cached",
    "_generate_groups_cached",
    "_generate_repositories_cached",
    "_generate_environments_cached",
    "_get_boards_in_organization_cached",
]


@pytest.mark.parametrize("method_name", CACHED_BACKING_METHODS)
def test_cached_backing_method_keys_differ_across_orgs(method_name: str) -> None:
    client_alpha = AzureDevopsClient(
        "https://dev.azure.com/org-alpha",
        PersonalAccessTokenAuthenticator("pat-alpha"),
        "port",
    )
    client_beta = AzureDevopsClient(
        "https://dev.azure.com/org-beta",
        PersonalAccessTokenAuthenticator("pat-beta"),
        "port",
    )
    func = getattr(client_alpha, method_name).__wrapped__

    key_alpha = hash_func(func, client_alpha, client_alpha._organization_base_url)
    key_beta = hash_func(func, client_beta, client_beta._organization_base_url)

    assert key_alpha != key_beta, (
        f"Cache keys for {method_name} must differ across org clients "
        f"(got {key_alpha} for both)."
    )


def test_cached_backing_method_key_stable_for_same_org() -> None:
    """Same org on two client instances should produce identical cache keys
    (so single-org deployments still benefit from the cache, and the
    instance identity genuinely doesn't matter — only the org URL does).
    """
    client_one = AzureDevopsClient(
        "https://dev.azure.com/only-org",
        PersonalAccessTokenAuthenticator("pat-one"),
        "port",
    )
    client_two = AzureDevopsClient(
        "https://dev.azure.com/only-org",
        PersonalAccessTokenAuthenticator("pat-two-different-instance"),
        "port",
    )
    func = client_one._generate_projects_cached.__wrapped__  # type: ignore[attr-defined]

    key_one = hash_func(func, client_one, client_one._organization_base_url)
    key_two = hash_func(func, client_two, client_two._organization_base_url)

    assert key_one == key_two
