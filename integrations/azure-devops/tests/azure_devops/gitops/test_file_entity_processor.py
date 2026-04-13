"""Tests for :func:`_get_client_for_entity` in file_entity_processor.

Covers the multi-org routing added in Task 8:
- Entity with a known ``__organizationUrl`` returns the per-org client
  from the manager
- Entity with an unknown ``__organizationUrl`` falls back to the legacy
  ``create_from_ocean_config_no_cache`` client and logs a warning
- Entity without ``__organizationUrl`` (single-org legacy path) uses
  the legacy factory — byte-identical to pre-multi-org behavior
"""

import json
from typing import Any, Dict, Generator

import pytest

from port_ocean.context.event import EventContext, _event_context_stack
from port_ocean.context.ocean import ocean

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.gitops.file_entity_processor import _get_client_for_entity


@pytest.fixture
def clean_event_context() -> Generator[None, None, None]:
    """Push a fresh event context with empty attributes so the client
    factories don't hit a pre-cached mock from another fixture."""
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


@pytest.fixture
def set_multi_org_mapping() -> Generator[Dict[str, str], None, None]:
    mapping = {
        "https://dev.azure.com/gitops-org-one": "pat-one",
        "https://dev.azure.com/gitops-org-two": "pat-two",
    }
    previous: Dict[str, Any] = {
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


def test_entity_with_known_org_url_returns_per_org_client(
    set_multi_org_mapping: Dict[str, str],
    clean_event_context: None,
) -> None:
    entity: Dict[str, Any] = {
        "id": "repo-123",
        "__organizationUrl": "https://dev.azure.com/gitops-org-one",
        "__organizationName": "gitops-org-one",
    }
    client = _get_client_for_entity(entity)
    assert isinstance(client, AzureDevopsClient)
    assert client.organization_url == "https://dev.azure.com/gitops-org-one"


def test_entity_with_unknown_org_url_falls_back_to_legacy(
    set_multi_org_mapping: Dict[str, str],
    clean_event_context: None,
) -> None:
    """If an entity carries an org URL that isn't in the manager (e.g.
    an org was removed from ``organizationTokenMapping`` between
    resync and GitOps processing), the handler must fall back to the
    legacy factory so the event doesn't crash."""
    ocean.integration_config["organization_url"] = "https://dev.azure.com/test-org"
    ocean.integration_config["personal_access_token"] = "test-pat"
    try:
        entity: Dict[str, Any] = {
            "id": "repo-123",
            "__organizationUrl": "https://dev.azure.com/deleted-org",
        }
        client = _get_client_for_entity(entity)
        assert client.organization_url == "https://dev.azure.com/test-org"
    finally:
        ocean.integration_config["organization_url"] = None
        ocean.integration_config["personal_access_token"] = None


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
    assert client.organization_url == "https://dev.azure.com/test-org"
