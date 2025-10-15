import types
from typing import Any

import pytest

from integrations.harbor.client import httpx

from integrations.harbor.client import HarborClient, HarborAuthMode
from port_ocean.utils import cache as cache_module


class _MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        return self._store.get(key)

    async def set(self, key: str, value: Any) -> None:
        self._store[key] = value


def _make_response(
    payload: Any,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    url: str = "https://harbor.example.com/api",
) -> httpx.Response:
    response = httpx.Response(
        status_code=status_code, headers=headers or {}, json=payload
    )
    response.request = httpx.Request("GET", url)
    return response


def _prepare_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    cache_provider = _MemoryCache()
    monkeypatch.setattr(
        cache_module,
        "ocean",
        types.SimpleNamespace(app=types.SimpleNamespace(cache_provider=cache_provider)),
        raising=False,
    )


@pytest.mark.asyncio
async def test_iter_pages_streams_until_depleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_cache(monkeypatch)

    responses = iter(
        [
            _make_response(
                {"items": [{"id": 1}, {"id": 2}]},
                headers={"X-Total-Count": "5"},
                url="https://harbor.example.com/api/projects",
            ),
            _make_response(
                {"items": [{"id": 3}, {"id": 4}]},
                headers={"X-Total-Count": "5"},
                url="https://harbor.example.com/api/projects",
            ),
            _make_response(
                {"items": [{"id": 5}]},
                headers={"X-Total-Count": "5"},
                url="https://harbor.example.com/api/projects",
            ),
        ]
    )

    observed_params: list[dict[str, Any]] = []

    async def _fake_get(
        self: HarborClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        del headers, timeout, path
        observed_params.append(params or {})
        return next(responses)

    monkeypatch.setattr(HarborClient, "get", _fake_get, raising=False)

    client = HarborClient(
        base_url="https://harbor.example.com",
        auth_mode=HarborAuthMode.ROBOT_TOKEN.value,
        robot_account="robot$port",
        robot_token="secret",
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in client.iter_pages("/api/projects", page_size=2):
        pages.append(page)

    assert pages == [
        [{"id": 1}, {"id": 2}],
        [{"id": 3}, {"id": 4}],
        [{"id": 5}],
    ]
    assert observed_params == [
        {"page": 1, "page_size": 2},
        {"page": 2, "page_size": 2},
        {"page": 3, "page_size": 2},
    ]


@pytest.mark.asyncio
async def test_iter_pages_respects_max_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_cache(monkeypatch)

    responses = iter(
        [
            _make_response(
                {"items": [{"id": 1}, {"id": 2}]},
                headers={"X-Total-Count": "4"},
                url="https://harbor.example.com/api/artifacts",
            ),
            _make_response(
                {"items": [{"id": 3}, {"id": 4}]},
                headers={"X-Total-Count": "4"},
                url="https://harbor.example.com/api/artifacts",
            ),
        ]
    )

    async def _fake_get(
        self: HarborClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        del params, headers, timeout, path
        return next(responses)

    monkeypatch.setattr(HarborClient, "get", _fake_get, raising=False)

    client = HarborClient(
        base_url="https://harbor.example.com",
        auth_mode=HarborAuthMode.ROBOT_TOKEN.value,
        robot_account="robot$port",
        robot_token="secret",
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in client.iter_pages("/api/artifacts", page_size=2, max_pages=1):
        pages.append(page)

    assert pages == [
        [{"id": 1}, {"id": 2}],
    ]


@pytest.mark.asyncio
async def test_iter_pages_stops_on_empty_page(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_cache(monkeypatch)

    responses = iter(
        [
            _make_response(
                {"items": []},
                headers={"X-Total-Count": "0"},
                url="https://harbor.example.com/api/vulnerabilities",
            ),
        ]
    )

    async def _fake_get(
        self: HarborClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        del params, headers, timeout, path
        return next(responses)

    monkeypatch.setattr(HarborClient, "get", _fake_get, raising=False)

    client = HarborClient(
        base_url="https://harbor.example.com",
        auth_mode=HarborAuthMode.ROBOT_TOKEN.value,
        robot_account="robot$port",
        robot_token="secret",
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in client.iter_pages("/api/vulnerabilities", page_size=2):
        pages.append(page)

    assert pages == []
