"""Tests for handle_event subscription-based routing and fallback behavior."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from azure_devops.webhooks import subscription_registry
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)


MOCK_ORG_URL = "https://dev.azure.com/testorg"
KNOWN_SUB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
UNKNOWN_SUB_ID = "00000000-0000-0000-0000-000000000000"


class _ConcreteProcessor(AzureDevOpsBaseWebhookProcessor):
    """Minimal concrete implementation for testing the base class."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["kind"]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def _handle_webhook_event(
        self, payload: Any, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(
            updated_raw_results=[{"id": "1"}],
            deleted_raw_results=[],
        )


def _make_processor() -> _ConcreteProcessor:
    fake_event = WebhookEvent(trace_id="t", payload={}, headers={})
    return _ConcreteProcessor(fake_event)


def _make_payload(subscription_id: str = KNOWN_SUB_ID) -> dict[str, object]:
    return {
        "subscriptionId": subscription_id,
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {"pushId": 14, "repository": {"id": "repo-1"}},
    }


def _setup_registry_and_manager(
    monkeypatch: pytest.MonkeyPatch,
    *,
    register_sub: bool = True,
    num_clients: int = 1,
) -> MagicMock:
    """Set up the subscription registry and mock the client manager."""
    subscription_registry.clear()

    mock_client = MagicMock()
    mock_client._organization_base_url = MOCK_ORG_URL

    if register_sub:
        subscription_registry.register(KNOWN_SUB_ID, mock_client)

    clients = [mock_client]
    if num_clients > 1:
        for i in range(1, num_clients):
            extra = MagicMock()
            extra._organization_base_url = f"https://dev.azure.com/org{i}"
            clients.append(extra)

    mock_manager = MagicMock()
    mock_manager.get_clients.return_value = clients
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor"
        ".AzureDevopsClientManager.create_from_ocean_config",
        lambda: mock_manager,
    )
    return mock_client


# ---------------------------------------------------------------------------
# Subscription registry unit tests
# ---------------------------------------------------------------------------


class TestSubscriptionRegistry:
    def test_register_and_get(self) -> None:
        subscription_registry.clear()
        client = MagicMock()
        subscription_registry.register("sub-1", client)
        assert subscription_registry.get_client("sub-1") is client

    def test_get_unknown_returns_none(self) -> None:
        subscription_registry.clear()
        assert subscription_registry.get_client("nonexistent") is None

    def test_register_many(self) -> None:
        subscription_registry.clear()
        client = MagicMock()
        subscription_registry.register_many(["a", "b", "c"], client)
        assert subscription_registry.get_client("a") is client
        assert subscription_registry.get_client("b") is client
        assert subscription_registry.get_client("c") is client
        assert subscription_registry.size() == 3

    def test_clear(self) -> None:
        subscription_registry.clear()
        subscription_registry.register("x", MagicMock())
        subscription_registry.clear()
        assert subscription_registry.size() == 0


# ---------------------------------------------------------------------------
# handle_event routing tests
# ---------------------------------------------------------------------------


class TestHandleEventRouting:
    @pytest.mark.asyncio
    async def test_known_subscription_routes_to_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When subscriptionId is in the registry, use that client."""
        _setup_registry_and_manager(monkeypatch, register_sub=True)
        processor = _make_processor()
        result = await processor.handle_event(_make_payload(KNOWN_SUB_ID), MagicMock())
        assert len(result.updated_raw_results) == 1
        item = result.updated_raw_results[0]
        assert item["__organizationUrl"] == MOCK_ORG_URL
        assert item["__organizationName"] == "testorg"

    @pytest.mark.asyncio
    async def test_unknown_subscription_single_client_uses_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown subscription + single client configured -> use that client."""
        _setup_registry_and_manager(monkeypatch, register_sub=False, num_clients=1)
        processor = _make_processor()
        result = await processor.handle_event(
            _make_payload(UNKNOWN_SUB_ID), MagicMock()
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["__organizationUrl"] == MOCK_ORG_URL

    @pytest.mark.asyncio
    async def test_unknown_subscription_multi_client_best_effort(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown subscription + multiple clients -> best-effort (raw payload)."""
        _setup_registry_and_manager(monkeypatch, register_sub=False, num_clients=3)
        processor = _make_processor()
        payload = _make_payload(UNKNOWN_SUB_ID)
        result = await processor.handle_event(payload, MagicMock())
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["pushId"] == 14
        assert "__organizationUrl" not in result.updated_raw_results[0]

    @pytest.mark.asyncio
    async def test_no_subscription_id_in_payload_single_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Payload missing subscriptionId + single client -> use default."""
        _setup_registry_and_manager(monkeypatch, register_sub=False, num_clients=1)
        processor = _make_processor()
        payload = {
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {"pushId": 5},
        }
        result = await processor.handle_event(payload, MagicMock())
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["__organizationUrl"] == MOCK_ORG_URL

    @pytest.mark.asyncio
    async def test_enrichment_skipped_when_no_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no client is found, results are returned without org enrichment."""
        _setup_registry_and_manager(monkeypatch, register_sub=False, num_clients=2)
        processor = _make_processor()
        result = await processor.handle_event(
            _make_payload(UNKNOWN_SUB_ID), MagicMock()
        )
        item = result.updated_raw_results[0]
        assert "__organizationUrl" not in item
        assert "__organizationName" not in item
