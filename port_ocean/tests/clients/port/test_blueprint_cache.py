import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.clients.port.blueprint_cache import BlueprintCache
from port_ocean.clients.port.mixins.blueprints import BlueprintClientMixin
from port_ocean.core.models import Blueprint, BlueprintRelation


def _make_blueprint(identifier: str = "test-bp") -> Blueprint:
    return Blueprint(
        identifier=identifier,
        title="Test",
        team=None,
        schema={"properties": {"name": {"type": "string"}}, "required": ["name"]},
        relations={
            "owner": BlueprintRelation(
                many=False, required=True, target="team", title="Owner"
            )
        },
    )


@pytest.fixture
def blueprint_cache() -> BlueprintCache:
    return BlueprintCache(ttl_seconds=60.0)


def test_blueprint_cache_returns_cached_entry_within_ttl(
    blueprint_cache: BlueprintCache,
) -> None:
    blueprint_cache.set(_make_blueprint())

    entry = blueprint_cache.get("test-bp")

    assert entry is not None
    assert entry.blueprint.identifier == "test-bp"


def test_blueprint_cache_expires_after_ttl(blueprint_cache: BlueprintCache) -> None:
    blueprint_cache.set(_make_blueprint())

    with pytest.MonkeyPatch.context() as monkeypatch:
        original_monotonic = time.monotonic
        start = original_monotonic()
        monkeypatch.setattr(time, "monotonic", lambda: start + 61)
        assert blueprint_cache.get("test-bp") is None


def test_blueprint_cache_invalidate_removes_entry(
    blueprint_cache: BlueprintCache,
) -> None:
    blueprint_cache.set(_make_blueprint())
    blueprint_cache.invalidate("test-bp")
    assert blueprint_cache.get("test-bp") is None


def test_blueprint_cache_invalidate_all_removes_all_entries(
    blueprint_cache: BlueprintCache,
) -> None:
    blueprint_cache.set(_make_blueprint("bp-a"))
    blueprint_cache.set(_make_blueprint("bp-b"))
    blueprint_cache.invalidate_all()
    assert blueprint_cache.get("bp-a") is None
    assert blueprint_cache.get("bp-b") is None


@pytest.fixture
async def blueprint_client() -> BlueprintClientMixin:
    auth = MagicMock()
    auth.api_url = "https://api.getport.io/v1"
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer token"})
    client = MagicMock()
    client.get = AsyncMock()
    return BlueprintClientMixin(
        auth=auth, client=client, blueprint_cache_ttl_seconds=60
    )


async def test_get_blueprint_uses_cache_on_second_call(
    blueprint_client: BlueprintClientMixin,
) -> None:
    blueprint_payload = {
        "identifier": "service",
        "title": "Service",
        "schema": {"properties": {}},
        "relations": {},
    }
    response = MagicMock()
    response.status_code = 200
    response.is_error = False
    response.json.return_value = {"blueprint": blueprint_payload}
    get_mock = AsyncMock(return_value=response)
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]

    first = await blueprint_client.get_blueprint("service", should_log=False)
    second = await blueprint_client.get_blueprint("service", should_log=False)

    assert first.identifier == "service"
    assert second.identifier == "service"
    assert get_mock.await_count == 1


async def test_patch_blueprint_invalidates_cache(
    blueprint_client: BlueprintClientMixin,
) -> None:
    blueprint_payload = {
        "identifier": "service",
        "title": "Service",
        "schema": {"properties": {}},
        "relations": {},
    }
    get_response = MagicMock()
    get_response.status_code = 200
    get_response.is_error = False
    get_response.json.return_value = {"blueprint": blueprint_payload}
    patch_response = MagicMock()
    patch_response.status_code = 200
    patch_response.is_error = False
    get_mock = AsyncMock(return_value=get_response)
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]
    blueprint_client.client.patch = AsyncMock(return_value=patch_response)  # type: ignore[method-assign]

    await blueprint_client.get_blueprint("service", should_log=False)
    await blueprint_client.patch_blueprint("service", {"title": "Updated"})
    await blueprint_client.get_blueprint("service", should_log=False)

    assert get_mock.await_count == 2
