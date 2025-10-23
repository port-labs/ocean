from typing import Any, Dict, List, cast

import httpx
import pytest

from azure_integration.clients.rest_client import AzureRestClient
from azure_integration.clients.base import AzureRequest


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
        method: str = "GET",
        url: str = "http://example.test",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}
        self.text = ""
        self._method = method
        self._url = url

    def json(self) -> Dict[str, Any]:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request(self._method, self._url)
            raise httpx.HTTPStatusError(
                "error",
                request=req,
                response=httpx.Response(
                    self.status_code, request=req, content=self.text.encode()
                ),
            )


class _FakeToken:
    token = "t"


class _FakeCredential:
    async def get_token(self, *args: Any, **kwargs: Any) -> _FakeToken:
        return _FakeToken()


class _FakeClient:
    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response

    async def request(
        self,
        *,
        method: str,
        url: str,
        params: Dict[str, Any] | None = None,
        json: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
    ) -> _FakeResponse:
        if isinstance(self._response, Exception):
            raise self._response
        # reflect method/url for error building
        self._response._method = method
        self._response._url = url
        return self._response


@pytest.mark.asyncio
async def test_make_request_success(monkeypatch: pytest.MonkeyPatch) -> None:
    cred = cast(Any, _FakeCredential())
    client = AzureRestClient(credential=cred, base_url="https://management.azure.com")
    fake_response = _FakeResponse(
        status_code=200,
        json_data={"ok": True},
        headers={"x-ms-ratelimit-remaining-tenant-reads": "80"},
    )
    fake_client = _FakeClient(fake_response)

    # Patch the property to return our fake client
    monkeypatch.setattr(AzureRestClient, "client", property(lambda self: fake_client))

    data = await client.make_request(AzureRequest(endpoint="/subscriptions"))
    assert data == {"ok": True}


@pytest.mark.asyncio
async def test_make_request_ignored_http_error_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cred = cast(Any, _FakeCredential())
    client = AzureRestClient(credential=cred, base_url="https://management.azure.com")
    # Prepare an HTTPStatusError with 404
    req = httpx.Request("GET", "https://management.azure.com/subscriptions")
    http_err = httpx.HTTPStatusError(
        "not found",
        request=req,
        response=httpx.Response(404, request=req, content=b"not found"),
    )
    fake_client = _FakeClient(http_err)

    monkeypatch.setattr(AzureRestClient, "client", property(lambda self: fake_client))

    data = await client.make_request(AzureRequest(endpoint="/subscriptions"))
    assert data == {}


@pytest.mark.asyncio
async def test_make_paginated_request_yields_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cred = cast(Any, _FakeCredential())
    client = AzureRestClient(credential=cred, base_url="https://management.azure.com")

    responses: List[Dict[str, Any]] = [
        {"value": [1, 2, 3], "nextLink": "next"},
        {"value": [4], "nextLink": None},
    ]

    async def fake_make_request(req: AzureRequest) -> Dict[str, Any]:
        return responses.pop(0)

    monkeypatch.setattr(client, "make_request", fake_make_request)

    batches: List[List[int]] = []
    async for batch in client.make_paginated_request(
        AzureRequest(endpoint="/resources", page_size=2, data_key="value")
    ):
        batches.append(batch)  # type: ignore[arg-type]

    assert batches == [[1, 2], [3, 4]]
