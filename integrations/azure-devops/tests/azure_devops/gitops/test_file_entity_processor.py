"""Tests for :func:`_get_client_for_entity` in file_entity_processor.

Covers the multi-org routing added for Service Principal mode:
- Entity with a known ``__organizationUrl`` returns the per-org client
  from the manager
- Entity with an unknown ``__organizationUrl`` falls back to the first
  configured client and logs a warning
- Entity without ``__organizationUrl`` (single-org path) uses the legacy
  factory — byte-identical to pre-multi-org behavior
"""

from typing import Any, Dict, Generator

import pytest

from port_ocean.context.event import EventContext, _event_context_stack
from port_ocean.context.ocean import ocean

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.gitops.file_entity_processor import _get_client_for_entity

_SP_KEYS = ("organization_urls", "client_id", "client_secret", "tenant_id")
_LEGACY_KEYS = ("organization_url", "personal_access_token")


@pytest.fixture
def clean_event_context() -> Generator[None, None, None]:
    """Push a fresh event context with empty attributes so the client
    factories don't hit a pre-cached mock from another fixture."""
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


@pytest.fixture
def set_multi_org_service_principal() -> Generator[list[str], None, None]:
    urls = [
        "https://dev.azure.com/gitops-org-one",
        "https://dev.azure.com/gitops-org-two",
    ]
    previous: Dict[str, Any] = {
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


def test_entity_with_known_org_url_returns_per_org_client(
    set_multi_org_service_principal: list[str],
    clean_event_context: None,
) -> None:
    entity: Dict[str, Any] = {
        "id": "repo-123",
        "__organizationUrl": "https://dev.azure.com/gitops-org-one",
        "__organizationName": "gitops-org-one",
    }
    client = _get_client_for_entity(entity)
    assert isinstance(client, AzureDevopsClient)
    assert client._organization_base_url == "https://dev.azure.com/gitops-org-one"


def test_entity_with_unknown_org_url_falls_back_to_first_client(
    set_multi_org_service_principal: list[str],
    clean_event_context: None,
) -> None:
    """If an entity carries an org URL that isn't in the manager (e.g.
    an org was removed from ``organizationUrls`` between resync and
    GitOps processing), the handler must fall back to the first
    configured client so the event doesn't crash."""
    entity: Dict[str, Any] = {
        "id": "repo-123",
        "__organizationUrl": "https://dev.azure.com/deleted-org",
    }
    client = _get_client_for_entity(entity)
    assert isinstance(client, AzureDevopsClient)
    assert client._organization_base_url in set_multi_org_service_principal


def test_entity_without_org_url_uses_legacy_client(
    clean_event_context: None,
) -> None:
    """Single-org deployment: entities don't carry ``__organizationUrl``
    because ``_enrich_webhook_results`` is a no-op when the webhook
    payload has no ``resourceContainers.*.baseUrl``. The GitOps handler
    should use the legacy factory — byte-identical to pre-multi-org
    behavior."""
    entity: Dict[str, Any] = {"id": "repo-123"}
    client = _get_client_for_entity(entity)
    assert isinstance(client, AzureDevopsClient)
    # From conftest.py's TEST_INTEGRATION_CONFIG:
    assert client._organization_base_url == "https://dev.azure.com/test-org"
