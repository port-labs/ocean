"""Tests for the EndpointCache file-based streaming cache."""

from typing import AsyncGenerator, Dict, List, Any
from pathlib import Path

import pytest

from http_server.helpers.endpoint_cache import (
    EndpointCache,
    make_cache_key,
    analyze_cacheable_endpoints,
    initialize_endpoint_cache,
    get_endpoint_cache,
    clear_endpoint_cache,
)
from http_server.overrides import (
    HttpServerResourceConfig,
    HttpServerSelector,
    ApiPathParameter,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
)


def _make_port_config() -> PortResourceConfig:
    return PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".id",
                title=".name",
                icon=None,
                blueprint='"test"',
                team=None,
                properties={},
                relations={},
            )
        ),
    )


def _make_resource(
    kind: str,
    method: str = "GET",
    query_params: dict[str, Any] | None = None,
    path_parameters: dict[str, Any] | None = None,
) -> HttpServerResourceConfig:
    selector = HttpServerSelector(
        query="true",
        method=method,
        query_params=query_params,
        path_parameters=path_parameters,
    )
    return HttpServerResourceConfig(
        kind=kind,
        selector=selector,
        port=_make_port_config(),
    )


class TestMakeCacheKey:
    def test_deterministic_for_same_inputs(self) -> None:
        key1 = make_cache_key("/api/v2/tickets.json", "GET")
        key2 = make_cache_key("/api/v2/tickets.json", "GET")
        assert key1 == key2

    def test_none_and_empty_dict_produce_same_key(self) -> None:
        key_none = make_cache_key("/api/tickets", "GET", query_params=None, headers=None)
        key_empty = make_cache_key("/api/tickets", "GET", query_params={}, headers={})
        assert key_none == key_empty

    def test_method_is_case_insensitive(self) -> None:
        key_upper = make_cache_key("/api/tickets", "GET")
        key_lower = make_cache_key("/api/tickets", "get")
        assert key_upper == key_lower

    def test_different_endpoints_produce_different_keys(self) -> None:
        key1 = make_cache_key("/api/v2/tickets.json", "GET")
        key2 = make_cache_key("/api/v2/orgs.json", "GET")
        assert key1 != key2

    def test_different_query_params_produce_different_keys(self) -> None:
        key1 = make_cache_key("/api/tickets", "GET", query_params={"status": "open"})
        key2 = make_cache_key("/api/tickets", "GET", query_params={"status": "closed"})
        assert key1 != key2


class TestAnalyzeCacheableEndpoints:
    def test_duplicate_kind_is_cacheable(self) -> None:
        resources = [
            _make_resource("/api/v2/tickets.json"),
            _make_resource("/api/v2/tickets.json"),
        ]
        cacheable = analyze_cacheable_endpoints(resources)
        expected_key = make_cache_key("/api/v2/tickets.json", "GET")
        assert expected_key in cacheable

    def test_single_use_endpoint_not_cacheable(self) -> None:
        resources = [
            _make_resource("/api/v2/tickets.json"),
            _make_resource("/api/v2/orgs.json"),
        ]
        cacheable = analyze_cacheable_endpoints(resources)
        assert len(cacheable) == 0

    def test_path_param_endpoint_matching_kind_is_cacheable(self) -> None:
        param = ApiPathParameter(
            endpoint="/api/v2/tickets.json",
            method="GET",
            field=".id",
            data_path=".tickets",
        )
        resources = [
            _make_resource("/api/v2/tickets.json"),
            _make_resource(
                "/api/v2/tickets/{ticket_id}/comments.json",
                path_parameters={"ticket_id": param},
            ),
        ]
        cacheable = analyze_cacheable_endpoints(resources)
        expected_key = make_cache_key("/api/v2/tickets.json", "GET")
        assert expected_key in cacheable

    def test_zendesk_example_identifies_tickets_as_cacheable(self) -> None:
        param = ApiPathParameter(
            endpoint="/api/v2/tickets.json",
            method="GET",
            field=".id",
            data_path=".tickets",
            filter="true",
        )
        resources = [
            _make_resource("/api/v2/tickets.json"),
            _make_resource(
                "/api/v2/tickets/{ticket_id}/comments.json",
                path_parameters={"ticket_id": param},
            ),
            _make_resource("/api/v2/tickets.json"),
            _make_resource("/api/v2/organizations.json"),
        ]
        cacheable = analyze_cacheable_endpoints(resources)
        tickets_key = make_cache_key("/api/v2/tickets.json", "GET")
        orgs_key = make_cache_key("/api/v2/organizations.json", "GET")
        assert tickets_key in cacheable
        assert orgs_key not in cacheable


class TestEndpointCacheWriteAndRead:
    @pytest.fixture()
    def cache(self, tmp_path: Path) -> EndpointCache:
        key = make_cache_key("/api/tickets", "GET")
        return EndpointCache(cacheable_keys={key}, cache_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_write_through_and_read_stream_roundtrip(self, cache: EndpointCache) -> None:
        key = make_cache_key("/api/tickets", "GET")
        batches = [[{"id": 1}, {"id": 2}], [{"id": 3}]]

        async def source() -> AsyncGenerator[List[Dict[str, Any]], None]:
            for b in batches:
                yield b

        written: list[list[dict[str, Any]]] = []
        async for batch in cache.write_through(key, source()):
            written.append(batch)
        assert written == batches

        read_back: list[list[dict[str, Any]]] = []
        async for batch in cache.read_stream(key):
            read_back.append(batch)
        assert read_back == batches

    @pytest.mark.asyncio
    async def test_has_cached_returns_true_after_write(self, cache: EndpointCache) -> None:
        key = make_cache_key("/api/tickets", "GET")
        assert not cache.has_cached(key)

        async def source() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"id": 1}]

        async for _ in cache.write_through(key, source()):
            pass

        assert cache.has_cached(key)

    @pytest.mark.asyncio
    async def test_clear_removes_files(self, cache: EndpointCache) -> None:
        key = make_cache_key("/api/tickets", "GET")

        async def source() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"id": 1}]

        async for _ in cache.write_through(key, source()):
            pass

        assert cache.has_cached(key)
        cache.clear()
        assert not cache.has_cached(key)


class TestGetOrFetch:
    @pytest.fixture()
    def cache(self, tmp_path: Path) -> EndpointCache:
        key = make_cache_key("/api/tickets", "GET")
        return EndpointCache(cacheable_keys={key}, cache_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_non_cacheable_endpoint_calls_fetch_directly(self, tmp_path: Path) -> None:
        cache = EndpointCache(cacheable_keys=set(), cache_dir=str(tmp_path))
        call_count = 0

        async def fetch_fn() -> AsyncGenerator[List[Dict[str, Any]], None]:
            nonlocal call_count
            call_count += 1
            yield [{"id": 1}]

        result: list[list[dict[str, Any]]] = []
        async for batch in cache.get_or_fetch(
            "/api/tickets", "GET", None, None, None, fetch_fn
        ):
            result.append(batch)

        assert result == [[{"id": 1}]]
        assert call_count == 1
        assert not cache.has_cached(make_cache_key("/api/tickets", "GET"))

    @pytest.mark.asyncio
    async def test_cacheable_endpoint_miss_then_hit(self, cache: EndpointCache) -> None:
        call_count = 0
        batches = [[{"id": 1}, {"id": 2}], [{"id": 3}]]

        async def fetch_fn() -> AsyncGenerator[List[Dict[str, Any]], None]:
            nonlocal call_count
            call_count += 1
            for b in batches:
                yield b

        first_result: list[list[dict[str, Any]]] = []
        async for batch in cache.get_or_fetch(
            "/api/tickets", "GET", None, None, None, fetch_fn
        ):
            first_result.append(batch)
        assert first_result == batches
        assert call_count == 1

        second_result: list[list[dict[str, Any]]] = []
        async for batch in cache.get_or_fetch(
            "/api/tickets", "GET", None, None, None, fetch_fn
        ):
            second_result.append(batch)
        assert second_result == batches
        assert call_count == 1


class TestModuleSingleton:
    def test_lifecycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import http_server.helpers.endpoint_cache as mod

        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path))

        resources = [
            _make_resource("/api/v2/tickets.json"),
            _make_resource("/api/v2/tickets.json"),
        ]
        cache = initialize_endpoint_cache(resources)
        assert cache is get_endpoint_cache()
        assert cache.is_cacheable(make_cache_key("/api/v2/tickets.json", "GET"))

        clear_endpoint_cache()
        assert get_endpoint_cache() is None
