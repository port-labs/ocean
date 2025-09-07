import pytest
import httpx


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code not in (404, 429):
            raise httpx.HTTPStatusError("error", request=None, response=None)


class _FakeAsyncClient:
    def __init__(self, responder):
        self._responder = responder
        self.timeout = httpx.Timeout(5.0)

    async def request(self, method: str, url: str, headers=None, params=None, json=None):
        return await self._responder(method, url, headers or {}, params or {}, json)


@pytest.mark.asyncio
async def test_rest_client_success_builds_full_url_and_headers(monkeypatch):
    from github.clients.rest_client import RestClient

    async def responder(method, url, headers, params, json):
        assert method == "GET"
        assert url == "https://api.github.com/repos/acme/r1/issues"
        assert headers.get("Authorization", "").startswith("Bearer ")
        return FakeResponse(200, payload=[{"ok": True}])

    client = RestClient(client=_FakeAsyncClient(responder))
    resp = await client.get("/repos/acme/r1/issues")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_rest_client_handles_404_gracefully(monkeypatch):
    from github.clients.rest_client import RestClient

    async def responder(method, url, headers, params, json):
        return FakeResponse(404, payload={"message": "Not Found"})

    client = RestClient(client=_FakeAsyncClient(responder))
    resp = await client.get("/repos/acme/missing")
    assert resp.status_code == 404
    assert resp.json()["message"] == "Not Found"


@pytest.mark.asyncio
async def test_rest_client_retries_on_429(monkeypatch):
    from github.clients.rest_client import RestClient

    calls = {"count": 0}

    async def responder(method, url, headers, params, json):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(429, payload=None, headers={"Retry-After": "0"})
        return FakeResponse(200, payload=[{"ok": True}])

    client = RestClient(client=_FakeAsyncClient(responder))
    resp = await client.get("/repos/acme/r1/issues")
    assert resp.status_code == 200
    assert calls["count"] == 2


