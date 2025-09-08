import asyncio
import pytest

from github_client import GithubClient


class FakeResponse:
    def __init__(self, status_code=200, headers=None, json_data=None, body=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self._json_data = json_data
        self._body = body

    def json(self):
        return self._json_data

    async def aread(self):
        return self._body


@pytest.fixture
def client():
    return GithubClient(token="t", base_url="https://api.github.test", max_concurrency=2)


@pytest.mark.asyncio
async def test_primary_rate_limit_retry(monkeypatch, client):
    calls = {"n": 0}
    reset_ts = 4_000_000_000
    seq = [
        FakeResponse(
            status_code=403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset_ts)},
        ),
        FakeResponse(status_code=200, json_data={"ok": True}),
    ]

    async def fake_request(method, url, headers=None, **kwargs):
        i = calls["n"]
        calls["n"] += 1
        return seq[min(i, len(seq) - 1)]

    client = GithubClient(token="t", http_request=fake_request)
    data = await client._request("GET", "https://api.github.com/anything")
    assert data["ok"] is True

    async def fast_sleep(_s):
        await asyncio.sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    out = await client._request("GET", "https://api.github.test/x")
    assert out == {"ok": True}
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_retry_after_header(monkeypatch, client):
    calls = {"n": 0}
    seq = [
        FakeResponse(status_code=429, headers={"retry-after": "3"}),
        FakeResponse(status_code=200, json_data={"ok": "done"}),
    ]

    async def fake_request(method, url, headers=None, **kwargs):
        i = calls["n"]; calls["n"] += 1
        return seq[min(i, len(seq) - 1)]
    _real_sleep = asyncio.sleep

    async def fast_sleep(_s):
        await _real_sleep(0)
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    client = GithubClient(token="t", http_request=fake_request)

    data = await client._request("GET", "https://api.github.com/anything")
    assert data["ok"] == "done"

    calls["n"] = 0

    out = await client._request("GET", "https://api.github.test/y")
    assert out == {"ok": "done"}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_secondary_rate_limit_exponential_backoff(monkeypatch, client):
    calls = {"n": 0}
    seq = [
        FakeResponse(status_code=403, headers={}),
        FakeResponse(status_code=403, headers={}),
        FakeResponse(status_code=200, json_data={"ok": 1}),
    ]

    async def fake_request(method, url, headers=None, **kwargs):
        i = calls["n"]; calls["n"] += 1
        return seq[min(i, len(seq) - 1)]

    sleeps = []
    _real_sleep = asyncio.sleep
    async def fake_sleep(s):
        sleeps.append(s)
        await _real_sleep(0)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = GithubClient(token="t", http_request=fake_request)

    data = await client._request("GET", "https://api.github.com/anything")
    assert data["ok"] == 1

    sleeps.clear()
    calls["n"] = 0

    out = await client._request("GET", "https://api.github.test/z")
    assert out == {"ok": 1}
    assert len(sleeps) >= 1