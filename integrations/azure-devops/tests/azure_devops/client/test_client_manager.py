import json
from typing import Any, Generator

import pytest

from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import ocean

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import (
    CLIENT_MANAGER_CACHE_KEY,
    AzureDevopsClientManager,
)


@pytest.fixture
def event_context() -> Generator[None, None, None]:
    """Push a fresh EventContext so manager caching can write to
    event.attributes without polluting other tests."""
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


@pytest.fixture
def set_legacy_single_org() -> Generator[None, None, None]:
    """Configure ocean.integration_config for single-org mode.
    Restores prior values on teardown."""
    previous: dict[str, Any] = {
        "organization_url": ocean.integration_config.get("organization_url"),
        "personal_access_token": ocean.integration_config.get("personal_access_token"),
        "organization_token_mapping": ocean.integration_config.get(
            "organization_token_mapping"
        ),
    }
    ocean.integration_config["organization_url"] = "https://dev.azure.com/legacy-org"
    ocean.integration_config["personal_access_token"] = "legacy-pat"
    ocean.integration_config["organization_token_mapping"] = None
    yield
    for key, value in previous.items():
        ocean.integration_config[key] = value


@pytest.fixture
def set_multi_org_mapping() -> Generator[dict[str, str], None, None]:
    """Configure ocean.integration_config for multi-org mode with two orgs.
    Yields the raw mapping dict for assertions. Restores prior values on teardown.
    """
    mapping = {
        "https://dev.azure.com/org-one": "pat-one",
        "https://dev.azure.com/org-two": "pat-two",
    }
    previous: dict[str, Any] = {
        "organization_url": ocean.integration_config.get("organization_url"),
        "personal_access_token": ocean.integration_config.get("personal_access_token"),
        "organization_token_mapping": ocean.integration_config.get(
            "organization_token_mapping"
        ),
    }
    ocean.integration_config["organization_url"] = None
    ocean.integration_config["personal_access_token"] = None
    ocean.integration_config["organization_token_mapping"] = json.dumps(mapping)
    yield mapping
    for key, value in previous.items():
        ocean.integration_config[key] = value


def test_legacy_single_org_builds_one_client(
    set_legacy_single_org: None, event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    clients = manager.get_clients()
    assert len(clients) == 1
    assert manager.is_multi_org is False
    client = clients[0]
    assert client.organization_url == "https://dev.azure.com/legacy-org"
    assert isinstance(client, AzureDevopsClient)


def test_legacy_single_org_client_lookup(
    set_legacy_single_org: None, event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    client = manager.get_client_for_org("https://dev.azure.com/legacy-org")
    assert client is not None
    assert isinstance(client, AzureDevopsClient)


def test_multi_org_builds_one_client_per_entry(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    clients = manager.get_clients()
    assert len(clients) == 2
    assert manager.is_multi_org is True
    urls = {client.organization_url for client in clients}
    assert urls == set(set_multi_org_mapping.keys())


def test_multi_org_client_lookup_by_exact_url(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    client = manager.get_client_for_org("https://dev.azure.com/org-one")
    assert client is not None


def test_multi_org_lookup_normalizes_trailing_slash(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    # Lookup with a trailing slash should resolve to the same client.
    client = manager.get_client_for_org("https://dev.azure.com/org-one/")
    assert client is not None


def test_multi_org_lookup_unknown_url_returns_none(
    set_multi_org_mapping: dict[str, str], event_context: None
) -> None:
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    assert manager.get_client_for_org("https://dev.azure.com/unknown-org") is None


def test_multi_org_with_trailing_slash_in_mapping_key(
    event_context: None,
) -> None:
    # Keys in organizationTokenMapping that carry a trailing slash are
    # normalized so lookups without the slash still hit.
    mapping = {"https://dev.azure.com/trailing/": "pat-trailing"}
    ocean.integration_config["organization_url"] = None
    ocean.integration_config["personal_access_token"] = None
    ocean.integration_config["organization_token_mapping"] = json.dumps(mapping)
    try:
        manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
        assert manager.get_client_for_org("https://dev.azure.com/trailing") is not None
    finally:
        ocean.integration_config["organization_token_mapping"] = None


def test_create_from_ocean_config_caches_within_event(
    set_legacy_single_org: None, event_context: None
) -> None:
    first = AzureDevopsClientManager.create_from_ocean_config()
    second = AzureDevopsClientManager.create_from_ocean_config()
    assert first is second
    # Sanity: the cache key is populated.
    from port_ocean.context.event import event as active_event

    assert active_event.attributes.get(CLIENT_MANAGER_CACHE_KEY) is first


def test_create_from_ocean_config_no_cache_returns_fresh_instance(
    set_legacy_single_org: None, event_context: None
) -> None:
    first = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    second = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    assert first is not second


def test_bad_config_raises_at_build(event_context: None) -> None:
    ocean.integration_config["organization_url"] = None
    ocean.integration_config["personal_access_token"] = None
    ocean.integration_config["organization_token_mapping"] = None
    try:
        with pytest.raises(ValueError, match="requires either"):
            AzureDevopsClientManager.create_from_ocean_config_no_cache()
    finally:
        # Restore so downstream tests don't fail due to polluted state.
        ocean.integration_config["organization_url"] = "https://dev.azure.com/test-org"
        ocean.integration_config["personal_access_token"] = "test-pat"
