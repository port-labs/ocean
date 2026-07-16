import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from port_ocean.clients.port.mixins.blueprints import BlueprintClientMixin


def _blueprint_api_response(
    identifier: str, *, response_identifier: str | None = None
) -> MagicMock:
    return MagicMock(
        status_code=200,
        is_error=False,
        json=MagicMock(
            return_value={
                "blueprint": {
                    "identifier": response_identifier or identifier,
                    "title": identifier,
                    "schema": {"properties": {}},
                    "relations": {},
                }
            }
        ),
    )


@pytest.fixture
def blueprint_client() -> BlueprintClientMixin:
    return BlueprintClientMixin(
        auth=MagicMock(
            api_url="https://api.getport.io/v1",
            headers=AsyncMock(return_value={"Authorization": "Bearer token"}),
        ),
        client=MagicMock(get=AsyncMock()),
        blueprint_cache_ttl_seconds=60,
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


async def test_get_blueprint_does_not_cache_failed_http_response(
    blueprint_client: BlueprintClientMixin,
) -> None:
    blueprint_client.client.get = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            raise_for_status=MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "error", request=MagicMock(), response=MagicMock()
                )
            )
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await blueprint_client.get_blueprint("test-bp", should_log=False)

    assert blueprint_client._blueprint_cache == {}


async def test_get_blueprint_caches_by_request_identifier_not_response_identifier(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(
        return_value=_blueprint_api_response(
            "requested-id", response_identifier="response-id"
        )
    )
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]

    blueprint = await blueprint_client.get_blueprint("requested-id", should_log=False)

    assert blueprint.identifier == "response-id"
    assert "requested-id" in blueprint_client._blueprint_cache
    assert "response-id" not in blueprint_client._blueprint_cache

    await blueprint_client.get_blueprint("requested-id", should_log=False)
    await blueprint_client.get_blueprint("response-id", should_log=False)

    assert get_mock.await_count == 2


async def test_create_blueprint_clears_cached_blueprint(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(return_value=_blueprint_api_response("service"))
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]
    blueprint_client.client.post = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            status_code=200,
            is_error=False,
            json=MagicMock(return_value={"blueprint": {"identifier": "service"}}),
        )
    )

    await blueprint_client.get_blueprint("service", should_log=False)
    await blueprint_client.create_blueprint({"identifier": "service"})
    await blueprint_client.get_blueprint("service", should_log=False)

    assert get_mock.await_count == 2


async def test_patch_blueprint_clears_cached_blueprint(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(return_value=_blueprint_api_response("service"))
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]
    blueprint_client.client.patch = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(status_code=200, is_error=False)
    )

    await blueprint_client.get_blueprint("service", should_log=False)
    await blueprint_client.patch_blueprint("service", {"title": "Updated"})
    await blueprint_client.get_blueprint("service", should_log=False)

    assert get_mock.await_count == 2


async def test_delete_blueprint_clears_cached_blueprint(
    blueprint_client: BlueprintClientMixin,
) -> None:
    get_mock = AsyncMock(return_value=_blueprint_api_response("service"))
    blueprint_client.client.get = get_mock  # type: ignore[method-assign]
    blueprint_client.client.delete = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(status_code=200, is_error=False)
    )

    await blueprint_client.get_blueprint("service", should_log=False)
    await blueprint_client.delete_blueprint("service")
    await blueprint_client.get_blueprint("service", should_log=False)

    assert get_mock.await_count == 2


async def test_blueprint_cache_clear_removes_all_entries(
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
