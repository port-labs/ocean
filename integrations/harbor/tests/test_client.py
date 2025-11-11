import math

import pytest

from integrations.harbor.client import HarborClient


def _make_client(**kwargs):
    defaults = {
        "base_url": "https://example.com",
        "auth_mode": "robot_token",
        "robot_account": "robot$account",
        "robot_token": "secret",
        "max_retries": kwargs.pop("max_retries", 3),
        "max_backoff_seconds": kwargs.pop("max_backoff_seconds", 30.0),
        "default_timeout": kwargs.pop("default_timeout", None),
        "max_concurrency": kwargs.pop("max_concurrency", None),
        "jitter_seconds": kwargs.pop("jitter_seconds", 0.0),
    }
    defaults.update(kwargs)
    return HarborClient(**defaults)


def test_robot_token_auth_header():
    client = _make_client()
    header = client._build_auth_header()
    assert header["Authorization"].startswith("Basic ")


def test_basic_auth_header():
    client = _make_client(auth_mode="basic", username="user", password="pass")
    header = client._build_auth_header()
    assert header["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_request_uses_semaphore(monkeypatch):
    calls = []

    async def handler(**kwargs):
        calls.append(kwargs)
        response = type(
            "Resp",
            (),
            {"status_code": 200, "text": "{}", "headers": {}, "json": lambda self: {}},
        )()
        return response

    client = _make_client(max_concurrency=1)

    class StubClient:
        async def request(self, *args, **kwargs):
            return await handler(**kwargs)

    client._client = StubClient()

    await client._request("GET", "/path")

    assert len(calls) == 1


def test_backoff_respects_retry_after():
    client = _make_client()
    assert client._get_backoff(2, "5") == 5


def test_backoff_with_jitter():
    client = _make_client(jitter_seconds=1.0)
    value = client._get_backoff(2, None)
    assert value >= client.backoff_factor * (2 ** (2 - 1))
    assert value <= client.max_backoff_seconds


@pytest.mark.asyncio
async def test_request_retries_on_http_error(monkeypatch):
    class DummyResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = "error"
            self.headers = {}

        def raise_for_status(self):
            from integrations.harbor.client import httpx

            raise httpx.HTTPStatusError("boom", request=None, response=self)

    attempts = 0

    async def handler(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            response = DummyResponse(500)
        else:
            response = DummyResponse(200)
            response.text = "{}"
            response.json = lambda: {}
        return response

    client = _make_client(max_retries=2)

    class StubClient:
        async def request(self, *args, **kwargs):
            return await handler(**kwargs)

    client._client = StubClient()

    response = await client._request("GET", "/test")
    assert response.status_code == 200
    assert attempts == 2
