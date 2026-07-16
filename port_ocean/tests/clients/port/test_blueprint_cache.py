import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.clients.port.mixins.blueprints import BlueprintClientMixin


def _blueprint_api_response(identifier: str) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.is_error = False
    response.json.return_value = {
        "blueprint": {
            "identifier": identifier,
            "title": identifier,
            "schema": {"properties": {}},
            "relations": {},
        }
    }
    return response


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
    get_mock = AsyncMock(return_value=_blueprint_api_response("test-bp"))
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]

    first = await blueprint_client.get_blueprint("test-bp", should_log=False)
    second = await blueprint_client.get_blueprint("test-bp", should_log=False)

    assert first.identifier == "test-bp"
    assert second.identifier == "test-bp"
    assert get_mock.await_count == 1


async def test_blueprint_cache_expires_after_ttl(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(return_value=_blueprint_api_response("test-bp"))
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]

    await blueprint_client.get_blueprint("test-bp", should_log=False)

    with pytest.MonkeyPatch.context() as monkeypatch:
        start = time.monotonic()
        monkeypatch.setattr(time, "monotonic", lambda: start + 61)
        await blueprint_client.get_blueprint("test-bp", should_log=False)

    assert get_mock.await_count == 2


async def test_blueprint_cache_invalidate_all_removes_all_entries(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(
        side_effect=[
            _blueprint_api_response("bp-a"),
            _blueprint_api_response("bp-b"),
        ]
    )
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]

    await blueprint_client.get_blueprint("bp-a", should_log=False)
    await blueprint_client.get_blueprint("bp-b", should_log=False)
    blueprint_client.clear_blueprint_cache()

    assert blueprint_client._blueprint_cache == {}


async def test_get_blueprint_uses_cache_on_second_call(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(return_value=_blueprint_api_response("service"))
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]

    first = await blueprint_client.get_blueprint("service", should_log=False)
    second = await blueprint_client.get_blueprint("service", should_log=False)

    assert first.identifier == "service"
    assert second.identifier == "service"
    assert get_mock.await_count == 1
