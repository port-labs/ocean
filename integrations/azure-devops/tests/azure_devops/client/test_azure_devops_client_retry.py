import json
from typing import Callable, List, cast
from unittest.mock import MagicMock

import httpx
import pytest

from azure_devops.client.auth import PatAuthProvider
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.base_client import MAX_TIMEMOUT_RETRIES
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

    client = AzureDevopsClient(
        MOCK_ORG_URL, PatAuthProvider("fake_pat"), "fake_username"
    )
    retry_transport = cast(RetryTransport, client._client._transport)
    retry_transport._wrapped_transport = httpx.MockTransport(handler)
    return client


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    # The 503 retry in _get_files_by_descriptors sleeps with exponential backoff;
    # skip those waits so tests stay fast.
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "azure_devops.client.azure_devops_client.asyncio.sleep", no_sleep
    )


@pytest.mark.asyncio
async def test_get_files_by_descriptors_retries_on_503(
    mock_context: PortOceanContext,
) -> None:
    # Verifies the per-call 503 retry loop in _get_files_by_descriptors:
    # the itemsbatch POST is re-sent on a 503 and the second response is parsed.
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
async def test_get_files_by_descriptors_does_not_retry_on_502(
    mock_context: PortOceanContext,
) -> None:
    # Only 503 is retried; other 5xx must surface immediately so that a real
    # upstream error isn't masked by retries that can't help.
    requests_seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(502)

    client = _make_client_with_mock_transport(mock_context, handler)
    descriptor = PathDescriptor(
        base_path="/src", recursion=RecursionLevel.FULL, pattern="/src/**"
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client._get_files_by_descriptors(
            MOCK_REPOSITORY, [descriptor], MOCK_BRANCH
        )

    assert exc_info.value.response.status_code == 502
    assert len(requests_seen) == 1


@pytest.mark.asyncio
async def test_get_files_by_descriptors_exhausts_503_retries_then_raises(
    mock_context: PortOceanContext,
) -> None:
    # If 503s persist past the budget, the method must raise instead of
    # silently returning [], otherwise persistent outages would look like
    # "no files in repository" and could cause false deletions.
    requests_seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(503)

    client = _make_client_with_mock_transport(mock_context, handler)
    descriptor = PathDescriptor(
        base_path="/src", recursion=RecursionLevel.FULL, pattern="/src/**"
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client._get_files_by_descriptors(
            MOCK_REPOSITORY, [descriptor], MOCK_BRANCH
        )

    assert exc_info.value.response.status_code == 503
    assert len(requests_seen) == MAX_TIMEMOUT_RETRIES + 1
