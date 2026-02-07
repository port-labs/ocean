from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from core.client import HarborClient
from core.webhook_handler import (
    validate_webhook_secret,
    process_webhook_event,
    _extract_event_data,
)


@pytest.fixture
def client() -> HarborClient:
    return HarborClient("http://localhost:8081", "admin", "Harbor12345")


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------


async def test_get_projects_single_page(httpx_mock, client):
    httpx_mock.add_response(
        json=[{"name": "opensource", "project_id": 1}],
        headers={"X-Total-Count": "1"},
    )

    batches = []
    async for batch in client.get_projects():
        batches.append(batch)

    assert len(batches) == 1
    assert batches[0][0]["name"] == "opensource"


async def test_get_projects_multiple_pages(httpx_mock, client):
    page_1 = [{"name": f"project-{i}", "project_id": i} for i in range(25)]
    page_2 = [{"name": "project-25", "project_id": 25}]

    httpx_mock.add_response(
        json=page_1,
        headers={"X-Total-Count": "26"},
    )
    httpx_mock.add_response(
        json=page_2,
        headers={"X-Total-Count": "26"},
    )

    batches = []
    async for batch in client.get_projects():
        batches.append(batch)

    assert len(batches) == 2
    assert len(batches[0]) == 25
    assert len(batches[1]) == 1
    assert batches[1][0]["name"] == "project-25"


async def test_get_projects_empty(httpx_mock, client):
    httpx_mock.add_response(
        json=[],
        headers={"X-Total-Count": "0"},
    )

    batches = []
    async for batch in client.get_projects():
        batches.append(batch)

    assert len(batches) == 0


# ---------------------------------------------------------------------------
# Users tests
# ---------------------------------------------------------------------------


async def test_get_users(httpx_mock, client):
    httpx_mock.add_response(
        json=[
            {"username": "admin", "user_id": 1, "email": "admin@harbor.local"},
            {"username": "dev", "user_id": 2, "email": "dev@harbor.local"},
        ],
        headers={"X-Total-Count": "2"},
    )

    batches = []
    async for batch in client.get_users():
        batches.append(batch)

    assert len(batches) == 1
    assert len(batches[0]) == 2
    assert batches[0][0]["username"] == "admin"


# ---------------------------------------------------------------------------
# Repositories tests
# ---------------------------------------------------------------------------


async def test_get_repositories(httpx_mock, client):
    httpx_mock.add_response(
        json=[
            {"name": "opensource/nginx", "id": 1, "artifact_count": 3},
            {"name": "opensource/redis", "id": 2, "artifact_count": 1},
        ],
        headers={"X-Total-Count": "2"},
    )

    batches = []
    async for batch in client.get_repositories("opensource"):
        batches.append(batch)

    assert len(batches) == 1
    assert batches[0][0]["name"] == "opensource/nginx"


# ---------------------------------------------------------------------------
# Artifacts tests
# ---------------------------------------------------------------------------


async def test_get_artifacts_enriches_repository_name(httpx_mock, client):
    httpx_mock.add_response(
        json=[
            {
                "digest": "sha256:abc123",
                "size": 12345,
                "tags": [{"name": "latest"}],
            }
        ],
        headers={"X-Total-Count": "1"},
    )

    batches = []
    async for batch in client.get_artifacts("opensource", "nginx"):
        batches.append(batch)

    assert len(batches) == 1
    assert batches[0][0]["repository_name"] == "opensource/nginx"
    assert batches[0][0]["digest"] == "sha256:abc123"


async def test_get_single_artifact(httpx_mock, client):
    httpx_mock.add_response(
        json={
            "digest": "sha256:abc123",
            "size": 12345,
            "tags": [{"name": "latest"}],
            "scan_overview": {},
        },
    )

    artifact = await client.get_single_artifact(
        "opensource", "nginx", "sha256:abc123"
    )

    assert artifact["digest"] == "sha256:abc123"
    assert artifact["repository_name"] == "opensource/nginx"


# ---------------------------------------------------------------------------
# Webhook secret validation tests
# ---------------------------------------------------------------------------


async def test_validate_webhook_secret_no_secret_configured():
    mock_request = MagicMock()
    with patch(
        "core.webhook_handler.ocean.integration_config",
        {"harbor_webhook_secret": None},
    ):
        result = await validate_webhook_secret(mock_request)
        assert result is True


async def test_validate_webhook_secret_valid():
    mock_request = MagicMock()
    mock_request.headers = {"Authorization": "mysecret123"}
    with patch(
        "core.webhook_handler.ocean.integration_config",
        {"harbor_webhook_secret": "mysecret123"},
    ):
        result = await validate_webhook_secret(mock_request)
        assert result is True


async def test_validate_webhook_secret_invalid():
    mock_request = MagicMock()
    mock_request.headers = {"Authorization": "wrongsecret"}
    with patch(
        "core.webhook_handler.ocean.integration_config",
        {"harbor_webhook_secret": "mysecret123"},
    ):
        result = await validate_webhook_secret(mock_request)
        assert result is False


# ---------------------------------------------------------------------------
# Webhook event extraction tests
# ---------------------------------------------------------------------------


def test_extract_event_data():
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "repository": {
                "namespace": "opensource",
                "name": "nginx",
                "repo_full_name": "opensource/nginx",
            },
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "tag": "latest",
                    "resource_url": "localhost:8081/opensource/nginx:latest",
                }
            ],
        },
    }

    project_name, repo_name, digest = _extract_event_data(payload)

    assert project_name == "opensource"
    assert repo_name == "nginx"
    assert digest == "sha256:abc123"


def test_extract_event_data_no_resources():
    payload = {
        "type": "DELETE_ARTIFACT",
        "event_data": {
            "repository": {
                "namespace": "opensource",
                "name": "nginx",
            },
        },
    }

    project_name, repo_name, digest = _extract_event_data(payload)

    assert project_name == "opensource"
    assert repo_name == "nginx"
    assert digest is None


# ---------------------------------------------------------------------------
# Webhook event processing tests
# ---------------------------------------------------------------------------


async def test_process_webhook_push_artifact():
    mock_client = AsyncMock(spec=HarborClient)
    mock_client.get_single_artifact.return_value = {
        "digest": "sha256:abc123",
        "repository_name": "opensource/nginx",
    }

    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "repository": {"namespace": "opensource", "name": "nginx"},
            "resources": [{"digest": "sha256:abc123"}],
        },
    }

    with patch("core.webhook_handler.ocean") as mock_ocean:
        mock_ocean.register_raw = AsyncMock()
        await process_webhook_event(payload, mock_client)

        mock_client.get_single_artifact.assert_called_once_with(
            "opensource", "nginx", "sha256:abc123"
        )
        mock_ocean.register_raw.assert_called_once_with(
            "artifact",
            [{"digest": "sha256:abc123", "repository_name": "opensource/nginx"}],
        )


async def test_process_webhook_delete_artifact():
    mock_client = AsyncMock(spec=HarborClient)

    payload = {
        "type": "DELETE_ARTIFACT",
        "event_data": {
            "repository": {"namespace": "opensource", "name": "nginx"},
            "resources": [{"digest": "sha256:abc123"}],
        },
    }

    with patch("core.webhook_handler.ocean") as mock_ocean:
        mock_ocean.unregister_raw = AsyncMock()
        await process_webhook_event(payload, mock_client)

        mock_client.get_single_artifact.assert_not_called()
        mock_ocean.unregister_raw.assert_called_once_with(
            "artifact",
            [{"repository_name": "opensource/nginx", "digest": "sha256:abc123"}],
        )


async def test_process_webhook_pull_artifact_ignored():
    mock_client = AsyncMock(spec=HarborClient)

    payload = {
        "type": "PULL_ARTIFACT",
        "event_data": {
            "repository": {"namespace": "opensource", "name": "nginx"},
            "resources": [{"digest": "sha256:abc123"}],
        },
    }

    with patch("core.webhook_handler.ocean") as mock_ocean:
        mock_ocean.register_raw = AsyncMock()
        mock_ocean.unregister_raw = AsyncMock()
        await process_webhook_event(payload, mock_client)

        mock_ocean.register_raw.assert_not_called()
        mock_ocean.unregister_raw.assert_not_called()
