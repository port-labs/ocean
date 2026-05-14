import json
from typing import Callable, List, cast
from unittest.mock import MagicMock

import httpx
import pytest

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.file_processing import PathDescriptor, RecursionLevel
from port_ocean.context.ocean import PortOceanContext
from port_ocean.helpers.retry import RetryTransport


MOCK_ORG_URL = "https://dev.azure.com/test_org"
MOCK_PROJECT_ID = "proj-id"
MOCK_REPOSITORY_ID = "repo-id"
MOCK_BRANCH = "main"
MOCK_REPOSITORY = {
    "id": MOCK_REPOSITORY_ID,
    "name": "test-repo",
    "project": {"id": MOCK_PROJECT_ID, "name": "test-proj"},
}


def _make_client_with_mock_transport(
    mock_context: PortOceanContext,
    handler: Callable[[httpx.Request], httpx.Response],
) -> AzureDevopsClient:
    # The conftest mock_context uses AsyncMock, so ocean.app.is_saas() returns a
    # coroutine (truthy) — which would make OceanAsyncClient wrap the transport in
    # IPBlockerTransport. Force is_saas to a sync False so the RetryTransport is
    # the outermost wrapper and we can swap the transport it wraps.
    mock_context.is_saas = MagicMock(return_value=False)  # type: ignore[attr-defined]

    client = AzureDevopsClient(MOCK_ORG_URL, "fake_pat", "fake_username")
    retry_transport = cast(RetryTransport, client._client._transport)
    retry_transport._wrapped_transport = httpx.MockTransport(handler)
    return client


@pytest.mark.asyncio
async def test_get_files_by_descriptors_retries_on_503(
    mock_context: PortOceanContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    # POST is not in RetryTransport's default retryable methods, so the only thing
    # that makes a 503 on itemsbatch retry is `extensions={"retryable": True}`.
    # This test fails if that extension is ever dropped from the call site.
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("port_ocean.helpers.retry.asyncio.sleep", no_sleep)

    expected_files = [
        {"path": "/src/app.py", "objectId": "abc"},
        {"path": "/src/util.py", "objectId": "def"},
    ]
    requests_seen: List[httpx.Request] = []
    responses = [
        httpx.Response(503),
        httpx.Response(200, json={"value": [expected_files]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return responses[min(len(requests_seen) - 1, len(responses) - 1)]

    client = _make_client_with_mock_transport(mock_context, handler)

    descriptor = PathDescriptor(
        base_path="/src", recursion=RecursionLevel.FULL, pattern="/src/**"
    )

    result = await client._get_files_by_descriptors(
        MOCK_REPOSITORY, [descriptor], MOCK_BRANCH
    )

    assert result == expected_files
    assert len(requests_seen) == 2
    assert {r.method for r in requests_seen} == {"POST"}
    assert all("itemsbatch" in str(r.url) for r in requests_seen)

    retried_payload = json.loads(requests_seen[1].content)
    assert retried_payload["itemDescriptors"][0]["path"] == "/src"
    assert retried_payload["itemDescriptors"][0]["version"] == MOCK_BRANCH
    assert retried_payload["itemDescriptors"][0]["versionType"] == "branch"


@pytest.mark.asyncio
async def test_get_files_by_descriptors_does_not_retry_post_without_retryable_extension(
    mock_context: PortOceanContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sanity check on the retry semantics this test file relies on:
    # POSTs without `extensions={"retryable": True}` must NOT be retried, otherwise
    # the positive test above would pass even if the extension was removed.
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("port_ocean.helpers.retry.asyncio.sleep", no_sleep)

    requests_seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(503)

    client = _make_client_with_mock_transport(mock_context, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await client.send_request(
            "POST",
            f"{MOCK_ORG_URL}/{MOCK_PROJECT_ID}/_apis/git/repositories/{MOCK_REPOSITORY_ID}/itemsbatch",
            data=json.dumps({"itemDescriptors": []}),
            headers={"Content-Type": "application/json"},
        )

    assert len(requests_seen) == 1
