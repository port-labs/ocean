"""Tests for the multi-org helpers on :class:`AzureDevOpsBaseWebhookProcessor`.

Covered behavior:
- ``_extract_org_url_from_payload`` pulls from
  ``resourceContainers.account.baseUrl`` first, then
  ``resourceContainers.collection.baseUrl``, and returns None when
  neither is present
- ``_get_client_for_webhook`` returns the per-org client in multi-org
  mode and falls back to the legacy client on miss or missing container
- ``_enrich_webhook_results`` annotates entities with
  ``__organizationUrl`` / ``__organizationName``, and is a no-op when
  the payload carries no org URL
- The base class's template-method ``handle_event`` delegates to
  ``_handle_webhook_event`` and enriches the result
"""

import json
from typing import Any, Dict, Generator
from unittest.mock import MagicMock

import pytest

from port_ocean.context.event import EventContext, _event_context_stack
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)


@pytest.fixture
def clean_event_context() -> Generator[None, None, None]:
    """Push an event context with empty attributes so client factories
    don't hit a pre-cached mock (as happens with the shared
    ``mock_event_context`` fixture from conftest.py)."""
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


class _ConcreteProcessor(AzureDevOpsBaseWebhookProcessor):
    """Minimal concrete subclass so tests can instantiate the base."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test-kind"]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # Return a fixture result the test can assert on; the base class's
        # template ``handle_event`` will enrich each entity in-place.
        return WebhookEventRawResults(
            updated_raw_results=[{"id": "entity-1"}],
            deleted_raw_results=[{"id": "entity-deleted"}],
        )


@pytest.fixture
def processor() -> _ConcreteProcessor:
    return _ConcreteProcessor(WebhookEvent(trace_id="t", payload={}, headers={}))


@pytest.fixture
def set_multi_org_mapping() -> Generator[Dict[str, str], None, None]:
    mapping = {
        "https://dev.azure.com/org-one": "pat-one",
        "https://dev.azure.com/org-two": "pat-two",
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


def test_extract_org_url_prefers_account_base_url() -> None:
    payload: EventPayload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/account-org/"},
            "collection": {"baseUrl": "https://dev.azure.com/collection-org/"},
        }
    }
    assert (
        AzureDevOpsBaseWebhookProcessor._extract_org_url_from_payload(payload)
        == "https://dev.azure.com/account-org"
    )


def test_extract_org_url_falls_back_to_collection_base_url() -> None:
    payload: EventPayload = {
        "resourceContainers": {
            "collection": {"baseUrl": "https://dev.azure.com/collection-org/"},
        }
    }
    assert (
        AzureDevOpsBaseWebhookProcessor._extract_org_url_from_payload(payload)
        == "https://dev.azure.com/collection-org"
    )


def test_extract_org_url_returns_none_when_no_base_url() -> None:
    payload: EventPayload = {"resourceContainers": {"project": {"id": "proj-123"}}}
    assert (
        AzureDevOpsBaseWebhookProcessor._extract_org_url_from_payload(payload) is None
    )


def test_extract_org_url_returns_none_when_no_containers() -> None:
    payload: EventPayload = {"resource": {"id": 123}}
    assert (
        AzureDevOpsBaseWebhookProcessor._extract_org_url_from_payload(payload) is None
    )


def test_get_client_for_webhook_returns_per_org_client_on_match(
    processor: _ConcreteProcessor,
    set_multi_org_mapping: Dict[str, str],
    clean_event_context: None,
) -> None:
    payload: EventPayload = {
        "resourceContainers": {"account": {"baseUrl": "https://dev.azure.com/org-one/"}}
    }
    client = processor._get_client_for_webhook(payload)
    assert isinstance(client, AzureDevopsClient)
    assert client.organization_url == "https://dev.azure.com/org-one"


def test_get_client_for_webhook_falls_back_when_container_missing(
    processor: _ConcreteProcessor,
    clean_event_context: None,
) -> None:
    """Single-org payload without resourceContainers falls through to the
    legacy factory. In the autouse test fixture this returns a client
    bound to the legacy test org URL."""
    payload: EventPayload = {"resource": {"id": 123}}
    client = processor._get_client_for_webhook(payload)
    assert isinstance(client, AzureDevopsClient)
    # From conftest.py's TEST_INTEGRATION_CONFIG:
    assert client.organization_url == "https://dev.azure.com/test-org"


def test_get_client_for_webhook_raises_on_unknown_org_multi_org(
    processor: _ConcreteProcessor,
    set_multi_org_mapping: Dict[str, str],
    clean_event_context: None,
) -> None:
    """If the extracted org URL isn't in the mapping and multiple orgs are
    configured, raise ValueError — the processor cannot determine which
    org to use."""
    payload: EventPayload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/unknown-org/"}
        }
    }
    with pytest.raises(ValueError, match="multiple organizations are configured"):
        processor._get_client_for_webhook(payload)


def test_enrich_webhook_results_annotates_both_lists(
    processor: _ConcreteProcessor,
) -> None:
    payload: EventPayload = {
        "resourceContainers": {"account": {"baseUrl": "https://dev.azure.com/my-org/"}}
    }
    result = WebhookEventRawResults(
        updated_raw_results=[{"id": "u1"}, {"id": "u2"}],
        deleted_raw_results=[{"id": "d1"}],
    )
    processor._enrich_webhook_results(result, payload)

    for entity in result.updated_raw_results + result.deleted_raw_results:
        assert entity["__organizationUrl"] == "https://dev.azure.com/my-org"
        assert entity["__organizationName"] == "my-org"


def test_enrich_webhook_results_is_noop_when_no_org_url(
    processor: _ConcreteProcessor,
) -> None:
    payload: EventPayload = {"resource": {"id": 1}}
    result = WebhookEventRawResults(
        updated_raw_results=[{"id": "u1"}],
        deleted_raw_results=[],
    )
    processor._enrich_webhook_results(result, payload)
    assert "__organizationUrl" not in result.updated_raw_results[0]
    assert "__organizationName" not in result.updated_raw_results[0]


@pytest.mark.asyncio
async def test_handle_event_delegates_and_enriches(
    processor: _ConcreteProcessor,
) -> None:
    """The base class's concrete handle_event should call the subclass's
    _handle_webhook_event and enrich every returned entity with org
    context (when the payload carries a base URL)."""
    payload: EventPayload = {
        "resourceContainers": {
            "account": {"baseUrl": "https://dev.azure.com/template-org/"}
        }
    }
    resource_config = MagicMock(spec=ResourceConfig)

    result = await processor.handle_event(payload, resource_config)

    assert len(result.updated_raw_results) == 1
    assert (
        result.updated_raw_results[0]["__organizationUrl"]
        == "https://dev.azure.com/template-org"
    )
    assert result.updated_raw_results[0]["__organizationName"] == "template-org"

    assert len(result.deleted_raw_results) == 1
    assert (
        result.deleted_raw_results[0]["__organizationUrl"]
        == "https://dev.azure.com/template-org"
    )
