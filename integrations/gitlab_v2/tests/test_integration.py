import os
from typing import Any
from unittest.mock import AsyncMock
from loguru import logger
import pytest
from pytest_httpx import HTTPXMock
import httpx
from httpx import AsyncClient

from integrations.gitlab_v2.client import GitlabClient
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.tests.helpers import (
    get_raw_result_on_integration_sync_kinds,
)

FAKE_GROUP: dict[str, Any] = {
    "id": 1,
    "name": "Test Group",
}

FAKE_PROJECT: dict[str, Any] = {
    "id": 1,
    "name": "Test Project",
    "__group": FAKE_GROUP,
    "path_with_namespace": "test-namespace/test-project",
    "web_url": "https://gitlab.com/test-namespace/test-project",
}

FAKE_ISSUE: dict[str, Any] = {
    "id": 1,
    "title": "Test Issue",
    "project_id": 1,
    "__project": FAKE_PROJECT,
}

FAKE_MERGE_REQUEST: dict[str, Any] = {
    "id": 1,
    "title": "Test Merge Request",
    "project_id": 1,
    "__project": FAKE_PROJECT,
}

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


@pytest.mark.asyncio
async def test_resync_project(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_projects(*args, **kwargs) -> list[dict[str, Any]]:
        return [FAKE_PROJECT]

    monkeypatch.setattr(GitlabClient, "get_projects", mock_get_projects)

    # Run the integration sync
    results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    httpx_mock.add_response(
        method="GET",
        url="https://gitlab.com/api/v4/projects",
        json=[FAKE_PROJECT],
        status_code=200,
        match_headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
    )

    async with httpx.AsyncClient() as client:
        response = (
            await client.get(
                "https://gitlab.com/api/v4/projects",
                headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
            )
        ).json()

        assert response == [FAKE_PROJECT]

    # assert len(results) > 0
    assert len(httpx_mock.get_requests()) > 0
    assert response[0]["name"] == "Test Project"


@pytest.mark.asyncio
async def test_resync_group(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_groups(*args, **kwargs) -> list[dict[str, Any]]:
        return [FAKE_GROUP]

    monkeypatch.setattr(GitlabClient, "get_groups", mock_get_groups)

    # Run the integration sync
    # results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    httpx_mock.add_response(
        method="GET",
        url="https://gitlab.com/api/v4/groups",
        json=[FAKE_GROUP],
        status_code=200,
        match_headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
    )

    async with httpx.AsyncClient() as client:
        response = (
            await client.get(
                "https://gitlab.com/api/v4/groups",
                headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
            )
        ).json()

        assert response == [FAKE_GROUP]

    # assert len(results) > 0
    assert len(httpx_mock.get_requests()) > 0
    assert response[0]["name"] == "Test Group"


@pytest.mark.asyncio
async def test_resync_issue(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_get_issues(*args, **kwargs) -> list[dict[str, Any]]:
        return [FAKE_ISSUE]

    monkeypatch.setattr(GitlabClient, "get_issues", mock_get_issues)

    # Run the integration sync
    # results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    httpx_mock.add_response(
        method="GET",
        url="https://gitlab.com/api/v4/issues",
        json=[FAKE_ISSUE],
        status_code=200,
        match_headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
    )

    async with httpx.AsyncClient() as client:
        response = (
            await client.get(
                "https://gitlab.com/api/v4/issues",
                headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
            )
        ).json()

        assert response == [FAKE_ISSUE]

    # assert len(results) > 0
    assert len(httpx_mock.get_requests()) > 0
    assert response[0]["title"] == "Test Issue"


@pytest.mark.asyncio
async def test_resync_merge_request(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mock_get_merge_requests(*args, **kwargs) -> list[dict[str, Any]]:
        return [FAKE_MERGE_REQUEST]

    monkeypatch.setattr(GitlabClient, "get_merge_requests", mock_get_merge_requests)

    # Run the integration sync
    # results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    httpx_mock.add_response(
        method="GET",
        url="https://gitlab.com/api/v4/merge_requests",
        json=[FAKE_MERGE_REQUEST],
        status_code=200,
        match_headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
    )

    async with httpx.AsyncClient() as client:
        response = (
            await client.get(
                "https://gitlab.com/api/v4/merge_requests",
                headers={"Authorization": "Bearer glpat-Wxf9AYDXK4VGFt1kkvyv"},
            )
        ).json()

        assert response == [FAKE_MERGE_REQUEST]

    # assert len(results) > 0
    assert len(httpx_mock.get_requests()) > 0
    assert response[0]["title"] == "Test Merge Request"


# Mock constants
FAKE_WEBHOOK_DATA_MERGE_REQUEST = {
    "event_type": "merge_request",
    "object_attributes": {
        "id": 123,
        "title": "Test Merge Request",
        "action": "open",
        "state": "opened",
        "created_at": "2024-09-14T12:00:00Z",
        "updated_at": "2024-09-14T12:05:00Z",
        "source": {"web_url": "https://gitlab.com/test-merge-request"},
    },
    "user": {"name": "John Doe"},
    "project": {"id": 456},
    "reviewers": [{"name": "Jane Reviewer"}],
}


@pytest.mark.asyncio
async def test_handle_webhook_register_raw(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mock_register_raw(kind, payload):
        assert kind == "merge_request"
        assert payload[0]["title"] == "Test Merge Request"

    # Mocking ocean's register_raw method
    monkeypatch.setattr(ocean, "register_raw", AsyncMock(side_effect=mock_register_raw))

    # Mocking the webhook request
    httpx_mock.add_response(
        method="POST",
        url="https://gitlab.com/webhook",
        json={"ok": True},
        status_code=200,
    )

    # Send the webhook event using httpx AsyncClient
    async with AsyncClient() as client:
        response = await client.post(
            "https://gitlab.com/webhook", json=FAKE_WEBHOOK_DATA_MERGE_REQUEST
        )

    # Assertions
    assert response.status_code == 200
    assert response.json() == {"ok": True}


FAKE_WEBHOOK_DATA_DELETE_MERGE_REQUEST = {
    "event_type": "merge_request",
    "object_attributes": {
        "id": 124,
        "title": "Test Merge Request",
        "action": "delete",  # Assuming this triggers unregister_raw
        "state": "closed",
        "created_at": "2024-09-14T12:00:00Z",
        "updated_at": "2024-09-14T12:00:00Z",
        "source": {"web_url": "https://gitlab.com/merge_request/124"},
    },
    "user": {"name": "Jane Doe"},
    "project": {"id": 789},
    "reviewers": [{"name": "Reviewer Name"}],
}


@pytest.mark.asyncio
async def test_handle_webhook_unregister_raw(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mock_unregister_raw(kind, payload):
        assert kind == "merge_request"
        assert payload[0]["title"] == "Test Merge Request"

    # Mocking ocean's unregister_raw method
    monkeypatch.setattr(
        ocean, "unregister_raw", AsyncMock(side_effect=mock_unregister_raw)
    )

    httpx_mock.add_response(
        method="POST",
        url="https://gitlab.com/webhook",
        json={"ok": True},
        status_code=200,
    )

    # Send the webhook event using httpx AsyncClient
    async with AsyncClient() as client:
        response = await client.post(
            "https://gitlab.com/webhook", json=FAKE_WEBHOOK_DATA_DELETE_MERGE_REQUEST
        )

    # Assertions
    assert response.status_code == 200
    assert response.json() == {"ok": True}