"""Unit tests for PortClient."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.clients.port.client import PortClient

TEST_BASE_URL = "https://api.example.com"
TEST_API_URL = f"{TEST_BASE_URL}/v1"


@pytest.fixture
def port_client() -> PortClient:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})

    http_client = MagicMock()
    http_client.get = AsyncMock()
    http_client.patch = AsyncMock()

    client = PortClient(
        base_url=TEST_BASE_URL,
        client_id="client-id",
        client_secret="client-secret",
        integration_identifier="my-integration",
        integration_type="github",
        integration_version="1.0.0",
    )
    client.auth = auth
    client.client = http_client
    return client


@pytest.mark.asyncio
async def test_get_org_id_returns_organization_id(port_client: PortClient) -> None:
    # Arrange
    response = MagicMock()
    response.is_error = False
    response.json.return_value = {"organization": {"id": "org-123"}}
    get_mock = AsyncMock(return_value=response)
    port_client.client.get = get_mock  # type: ignore[method-assign]

    # Act
    with patch("port_ocean.clients.port.client.handle_port_status_code"):
        org_id = await port_client.get_org_id()

    # Assert
    assert org_id == "org-123"
    get_mock.assert_called_once_with(
        f"{TEST_API_URL}/organization",
        headers={"Authorization": "Bearer test-token"},
    )


@pytest.mark.asyncio
async def test_patch_probe_health_result_sends_patch_request(
    port_client: PortClient,
) -> None:
    # Arrange
    response = MagicMock()
    response.is_success = True
    patch_mock = AsyncMock(return_value=response)
    port_client.client.patch = patch_mock  # type: ignore[method-assign]
    body: dict[str, Any] = {
        "status": "IN_PROGRESS",
        "checks": [],
    }

    # Act
    with patch("port_ocean.clients.port.client.handle_port_status_code"):
        await port_client.patch_probe_health_result("org-123", "probe-1", body)

    # Assert
    patch_mock.assert_called_once_with(
        f"{TEST_API_URL}/org/org-123/probe/probe-1",
        headers={"Authorization": "Bearer test-token"},
        json=body,
    )
