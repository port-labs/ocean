from typing import Any, AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest

from port_ocean.context.event import _event_context_stack, EventContext
from port_ocean.context.ocean import ocean

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.helpers.multi_org import (
    CONCURRENT_ORG_RESYNCS,
    iterate_per_organization,
)

_SP_KEYS = ("organization_urls", "client_id", "client_secret", "tenant_id")
_LEGACY_KEYS = ("organization_url", "personal_access_token")


def _snapshot_config() -> dict[str, Any]:
    return {key: ocean.integration_config.get(key) for key in _LEGACY_KEYS + _SP_KEYS}


def _restore_config(snapshot: dict[str, Any]) -> None:
    for key, value in snapshot.items():
        ocean.integration_config[key] = value


def _set_sp_mode(urls: list[str]) -> None:
    for key in _LEGACY_KEYS:
        ocean.integration_config[key] = None
    ocean.integration_config["organization_urls"] = urls
    ocean.integration_config["client_id"] = "sp-client-id"
    ocean.integration_config["client_secret"] = "sp-client-secret"
    ocean.integration_config["tenant_id"] = "sp-tenant-id"


@pytest.fixture
def event_context() -> Generator[None, None, None]:
    ctx = EventContext(event_type="TEST", attributes={})
    _event_context_stack.push(ctx)
    yield
    _event_context_stack.pop()


@pytest.fixture
def set_legacy_single_org() -> Generator[None, None, None]:
    previous = _snapshot_config()
    ocean.integration_config["organization_url"] = "https://dev.azure.com/single-org"
    ocean.integration_config["personal_access_token"] = "single-pat"
    for key in _SP_KEYS:
        ocean.integration_config[key] = None
    yield
    _restore_config(previous)


@pytest.fixture
def set_multi_org_service_principal() -> Generator[list[str], None, None]:
    previous = _snapshot_config()
    urls = [
        "https://dev.azure.com/org-one",
        "https://dev.azure.com/org-two",
    ]
    _set_sp_mode(urls)
    yield urls
    _restore_config(previous)


@pytest.mark.asyncio
async def test_single_org_yields_enriched_batches(
    set_legacy_single_org: None, event_context: None
) -> None:
    async def handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [{"id": "p1"}, {"id": "p2"}]
        yield [{"id": "p3"}]

    results: list[list[dict[str, Any]]] = []
    async for batch in iterate_per_organization(handler):
        results.append(batch)

    assert len(results) == 2
    assert [item["id"] for item in results[0]] == ["p1", "p2"]
    assert [item["id"] for item in results[1]] == ["p3"]

    for batch in results:
        for entity in batch:
            assert entity["__organizationUrl"] == "https://dev.azure.com/single-org"
            assert entity["__organizationName"] == "single-org"


@pytest.mark.asyncio
async def test_single_org_propagates_handler_exception(
    set_legacy_single_org: None, event_context: None
) -> None:
    class BoomError(RuntimeError):
        pass

    async def handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [{"id": "p1"}]
        raise BoomError("simulated resync failure")

    with pytest.raises(BoomError, match="simulated resync failure"):
        async for _ in iterate_per_organization(handler):
            pass


@pytest.mark.asyncio
async def test_multi_org_yields_batches_from_every_org(
    set_multi_org_service_principal: list[str], event_context: None
) -> None:
    calls: list[str] = []

    async def handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        calls.append(client._organization_base_url)
        yield [{"id": f"{client._organization_base_url}::entity"}]

    results: list[dict[str, Any]] = []
    async for batch in iterate_per_organization(handler):
        results.extend(batch)

    assert sorted(calls) == sorted(set_multi_org_service_principal)

    per_org = {entity["__organizationUrl"]: entity for entity in results}
    assert set(per_org.keys()) == set(set_multi_org_service_principal)
    assert per_org["https://dev.azure.com/org-one"]["__organizationName"] == "org-one"
    assert per_org["https://dev.azure.com/org-two"]["__organizationName"] == "org-two"


@pytest.mark.asyncio
async def test_multi_org_error_isolation_one_failing_org(
    set_multi_org_service_principal: list[str], event_context: None
) -> None:
    async def handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if client._organization_base_url == "https://dev.azure.com/org-one":
            raise RuntimeError("org-one is broken")
        yield [{"id": "ok-from-org-two"}]

    results: list[dict[str, Any]] = []
    async for batch in iterate_per_organization(handler):
        results.extend(batch)

    assert len(results) == 1
    assert results[0]["id"] == "ok-from-org-two"
    assert results[0]["__organizationUrl"] == "https://dev.azure.com/org-two"


@pytest.mark.asyncio
async def test_multi_org_respects_concurrency_bound(
    event_context: None,
) -> None:
    """With CONCURRENT_ORG_RESYNCS=3 (the production constant) and 7 configured
    orgs, at most CONCURRENT_ORG_RESYNCS handler coroutines should be in flight
    at any one moment.
    """
    urls = [f"https://dev.azure.com/org-{i}" for i in range(7)]
    previous = _snapshot_config()
    _set_sp_mode(urls)

    in_flight = 0
    max_in_flight = 0

    try:

        async def handler(
            client: AzureDevopsClient,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            yield [{"id": client._organization_base_url}]
            in_flight -= 1

        batches: list[list[dict[str, Any]]] = []
        async for batch in iterate_per_organization(handler):
            batches.append(batch)

        assert len(batches) == 7, "Every org should have yielded a batch."
        assert max_in_flight <= CONCURRENT_ORG_RESYNCS
    finally:
        _restore_config(previous)


@pytest.mark.asyncio
async def test_empty_manager_yields_nothing(
    monkeypatch: pytest.MonkeyPatch, event_context: None
) -> None:
    empty_manager = MagicMock(spec=AzureDevopsClientManager)
    empty_manager.get_clients.return_value = []
    monkeypatch.setattr(
        "azure_devops.helpers.multi_org.AzureDevopsClientManager.create_from_ocean_config",
        lambda: empty_manager,
    )

    async def handler(
        client: AzureDevopsClient,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [{"id": "never"}]

    results: list[list[dict[str, Any]]] = []
    async for batch in iterate_per_organization(handler):
        results.append(batch)

    assert results == []
