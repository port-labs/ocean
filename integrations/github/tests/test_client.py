import pytest
from typing import Any, Optional
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from client import GitHubClient

TEST_INTEGRATION_CONFIG: dict[str, str] = {
    "token": "mock-github-token",
    "organization": "test-org",
    "webhook_base_url": "https://app.example.com",
}

TEST_DATA: dict[str, list[dict[str, Any]]] = {
    "repositories": [
        {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
        {"id": 2, "name": "repo2", "full_name": "test-org/repo2"}
    ],
    "pull_requests": [
        {"id": 101, "number": 1, "title": "First PR", "state": "open"},
        {"id": 102, "number": 2, "title": "Second PR", "state": "closed"}
    ],
    "issues": [
        {"id": 201, "number": 1, "title": "Bug report", "state": "open"},
        {"id": 202, "number": 2, "title": "Feature request", "state": "closed"}
    ]
}

@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "token": TEST_INTEGRATION_CONFIG["token"],
            "organization": TEST_INTEGRATION_CONFIG["organization"],
            "webhook_base_url": TEST_INTEGRATION_CONFIG["webhook_base_url"],
            "github_api_version": "2022-11-28",

        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = TEST_INTEGRATION_CONFIG["webhook_base_url"]
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(**TEST_INTEGRATION_CONFIG)

@pytest.mark.asyncio
class TestGitHubClient:
    async def test_rate_limiting(self, client: GitHubClient) -> None:
        # Test rate limit handling
        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(pytest.importorskip("time").time()) + 60)
        }
        mock_response.status_code = 429

        with patch("port_ocean.utils.http_async_client.request", side_effect=[mock_response, MagicMock()]):
            await client._send_api_request("/test")
            # Should not raise an exception and handle rate limiting

    async def test_create_webhooks_if_not_exists(self, client: GitHubClient) -> None:
        # Test webhook creation when none exist
        list_hooks_response = MagicMock()
        list_hooks_response.json.return_value = []

        create_hook_response = MagicMock()
        create_hook_response.json.return_value = {"id": "new-hook"}

        with patch("port_ocean.utils.http_async_client.request", 
                  side_effect=[list_hooks_response, create_hook_response]):
            await client.create_webhooks_if_not_exists()

        # Test when webhook already exists
        existing_hook_response = MagicMock()
        existing_hook_response.json.return_value = [{
            "config": {
                "url": f"{TEST_INTEGRATION_CONFIG['webhook_base_url']}/integration/webhook"
            }
        }]

        with patch("port_ocean.utils.http_async_client.request",
                  return_value=existing_hook_response):
            await client.create_webhooks_if_not_exists() 