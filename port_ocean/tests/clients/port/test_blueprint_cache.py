import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.clients.port.mixins.blueprints import (
    BlueprintCacheEntry,
    BlueprintClientMixin,
)
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


def _seed_cache(blueprint_client: BlueprintClientMixin, blueprint: Blueprint) -> None:
    blueprint_client._blueprint_cache[blueprint.identifier] = BlueprintCacheEntry(
        blueprint=blueprint
    )


@pytest.fixture
def blueprint_client() -> BlueprintClientMixin:
    auth = MagicMock()
    auth.api_url = "https://api.getport.io/v1"
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer token"})
    client = MagicMock()
    client.get = AsyncMock()
    return BlueprintClientMixin(
        auth=auth, client=client, blueprint_cache_ttl_seconds=60
    )


async def test_blueprint_cache_returns_cached_entry_within_ttl(
    blueprint_client: BlueprintClientMixin,
) -> None:
    _seed_cache(blueprint_client, _make_blueprint())

    cached_blueprint = await blueprint_client.get_blueprint("test-bp", should_log=False)

    assert cached_blueprint.identifier == "test-bp"
    blueprint_client.client.get.assert_not_called()  # type: ignore[attr-defined]


async def test_blueprint_cache_expires_after_ttl(
    blueprint_client: BlueprintClientMixin,
) -> None:
    blueprint = _make_blueprint()
    _seed_cache(blueprint_client, blueprint)
    response = MagicMock()
    response.status_code = 200
    response.is_error = False
    response.json.return_value = {
        "blueprint": {
            "identifier": blueprint.identifier,
            "title": blueprint.title,
            "schema": blueprint.properties_schema,
            "relations": {},
        }
    }
    blueprint_client.client.get = AsyncMock(return_value=response)  # type: ignore[method-assign]

    with pytest.MonkeyPatch.context() as monkeypatch:
        original_monotonic = time.monotonic
        start = original_monotonic()
        monkeypatch.setattr(time, "monotonic", lambda: start + 61)
        await blueprint_client.get_blueprint("test-bp", should_log=False)

    blueprint_client.client.get.assert_awaited_once()


def test_blueprint_cache_invalidate_all_removes_all_entries(
    blueprint_client: BlueprintClientMixin,
) -> None:
    _seed_cache(blueprint_client, _make_blueprint("bp-a"))
    _seed_cache(blueprint_client, _make_blueprint("bp-b"))
    blueprint_client.invalidate_all_cached_blueprints()
    assert blueprint_client._blueprint_cache == {}


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
