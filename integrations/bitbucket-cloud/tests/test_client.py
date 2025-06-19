import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from httpx import AsyncClient, HTTPStatusError
from port_ocean.context.event import event_context
from typing import Any, AsyncIterator, Generator
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture
def mock_http_client() -> AsyncClient:
    """Create a mock HTTP client."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def mock_integration_config() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
        "bitbucket_username": "test_user",
        "bitbucket_app_password": "test_password",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture
async def mock_client(
    mock_integration_config: dict[str, str], mock_http_client: AsyncClient
) -> BitbucketClient:
    """Create BitbucketClient using create_from_ocean_config."""
    with patch("bitbucket_cloud.client.http_async_client", mock_http_client):
        return BitbucketClient.create_from_ocean_config()


@pytest.mark.asyncio
async def test_client_init_with_token() -> None:
    """Test client initialization with token auth."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
        "bitbucket_workspace_token": "test_token",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            client = BitbucketClient.create_from_ocean_config()
            assert "Authorization" in client.headers
            assert client.headers["Authorization"] == "Bearer test_token"


@pytest.mark.asyncio
async def test_client_init_with_app_password(
    mock_integration_config: dict[str, str]
) -> None:
    """Test client initialization with app password auth."""
    with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
        client = BitbucketClient.create_from_ocean_config()
        assert "Authorization" in client.headers
        assert "Basic" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_no_auth() -> None:
    """Test client initialization with no auth raises error."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            with pytest.raises(MissingIntegrationCredentialException) as exc_info:
                BitbucketClient.create_from_ocean_config()
            assert (
                "Either workspace token or both username and app password must be provided"
                in str(exc_info.value)
            )


@pytest.mark.asyncio
async def test_send_api_request_success(mock_client: BitbucketClient) -> None:
    """Test successful API request."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    with patch.object(
        mock_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client._send_api_request(
            f"{mock_client.base_url}/test/endpoint"
        )
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params=None,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_with_params(mock_client: BitbucketClient) -> None:
    """Test API request with query parameters."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    params = {"page": 1, "pagelen": 100}
    with patch.object(
        mock_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client._send_api_request(
            f"{mock_client.base_url}/test/endpoint", params=params
        )
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params=params,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_error(mock_client: BitbucketClient) -> None:
    """Test API request with error response and error message extraction."""
    # Create a mock response with a 400 status code and error message
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": {"message": "Test error message"}}

    original_error = HTTPStatusError(
        "400 Client Error", request=MagicMock(), response=mock_response
    )
    mock_response.raise_for_status.side_effect = original_error

    with (
        patch.object(
            mock_client.client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch("bitbucket_cloud.client.logger.error") as mock_logger,
    ):
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_client._send_api_request(f"{mock_client.base_url}/test/endpoint")

        assert exc_info.value == original_error
        mock_logger.assert_called_once_with("Bitbucket API error: 400 Client Error")


@pytest.mark.asyncio
async def test_send_paginated_api_request(mock_client: BitbucketClient) -> None:
    """Test paginated API request."""
    page1 = {
        "values": [{"id": 1}, {"id": 2}],
        "next": "https://api.bitbucket.org/2.0/test/endpoint?page=2",
    }
    page2 = {"values": [{"id": 3}], "next": None}
    with patch.object(
        mock_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2]
        batches = []
        async for batch in mock_client._send_paginated_api_request(
            f"{mock_client.base_url}/test/endpoint"
        ):
            batches.append(batch)

        assert batches[0] == [{"id": 1}, {"id": 2}]
        assert batches[1] == [{"id": 3}]
        assert len(batches) == 2

        all_results = [item for batch in batches for item in batch]
        assert len(all_results) == 3
        assert [item["id"] for item in all_results] == [1, 2, 3]

        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_projects(mock_client: BitbucketClient) -> None:
    """Test getting projects."""
    mock_data = {"values": [{"key": "TEST", "name": "Test Project"}]}
    async with event_context("test_event"):
        with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for projects in mock_client.get_projects():
                assert projects == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/workspaces/test_workspace/projects"
            )


@pytest.mark.asyncio
async def test_get_repositories(mock_client: BitbucketClient) -> None:
    """Test getting repositories."""
    mock_data = {"values": [{"slug": "test-repo", "name": "Test Repo"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_fetch_paginated_api_with_rate_limiter"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for repos in mock_client.get_repositories():
                assert repos == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/test_workspace", params=None
            )


@pytest.mark.asyncio
async def test_get_directory_contents(mock_client: BitbucketClient) -> None:
    """Test getting directory contents."""
    mock_dir_data = {"values": [{"type": "commit_directory", "path": "src"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_fetch_paginated_api_with_rate_limiter"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_dir_data["values"]

            mock_paginated.return_value = mock_generator()
            async for contents in mock_client.get_directory_contents(
                "test-repo", "main", "", 2
            ):
                assert contents == mock_dir_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/{mock_client.workspace}/test-repo/src/main/",
                params={"max_depth": 2, "pagelen": 100},
            )


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client: BitbucketClient) -> None:
    """Test getting pull requests."""
    mock_data = {"values": [{"id": 1, "title": "Test PR"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_fetch_paginated_api_with_rate_limiter"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for prs in mock_client.get_pull_requests("test-repo"):
                assert prs == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/{mock_client.workspace}/test-repo/pullrequests",
                params={"state": "OPEN", "pagelen": 50},
            )


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.oauth_access_token_file_path = None
        mock_ocean_app.config.integration.config = {
            "bitbucket_workspace": "test-workspace",
            "bitbucket_host_url": "https://api.bitbucket.org/2.0",
            "bitbucket_username": "test-user",
            "bitbucket_app_password": "test-password",
            "bitbucket_workspace_token": "test-token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        mock_ocean_app.load_external_oauth_access_token = MagicMock(return_value=None)
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


class TestBitbucketClient:
    def test_client_initialization_with_workspace_token(self) -> None:
        """Test BitbucketClient initialization with workspace token."""
        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            client = BitbucketClient(
                workspace="test-workspace",
                host="https://api.bitbucket.org/2.0",
                workspace_token="test-token",
            )
            assert client.workspace == "test-workspace"
            assert client.base_url == "https://api.bitbucket.org/2.0"
            assert "Authorization" in client.headers
            assert client.headers["Authorization"] == "Bearer test-token"

    def test_client_initialization_with_username_password(self) -> None:
        """Test BitbucketClient initialization with username and app password."""
        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            client = BitbucketClient(
                workspace="test-workspace",
                host="https://api.bitbucket.org/2.0",
                username="test-user",
                app_password="test-password",
            )
            assert client.workspace == "test-workspace"
            assert client.base_url == "https://api.bitbucket.org/2.0"
            assert "Authorization" in client.headers
            assert client.headers["Authorization"].startswith("Basic ")

    def test_client_initialization_oauth_enabled(self) -> None:
        """Test BitbucketClient initialization with OAuth enabled."""
        with (
            patch.object(BitbucketClient, "is_oauth_enabled", return_value=True),
            patch.object(BitbucketClient, "external_access_token", "oauth-token"),
        ):
            client = BitbucketClient(
                workspace="test-workspace",
                host="https://api.bitbucket.org/2.0",
                workspace_token="test-token",
            )
            assert "Authorization" in client.headers
            assert client.headers["Authorization"] == "Bearer oauth-token"

    def test_client_initialization_missing_credentials(self) -> None:
        """Test BitbucketClient initialization fails with missing credentials."""
        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            with pytest.raises(MissingIntegrationCredentialException):
                BitbucketClient(
                    workspace="test-workspace",
                    host="https://api.bitbucket.org/2.0",
                )

    def test_oauth_fallback_to_workspace_token(self) -> None:
        """Test OAuth fallback to workspace token when external token is not available."""
        with (
            patch.object(BitbucketClient, "is_oauth_enabled", return_value=True),
            patch.object(
                BitbucketClient,
                "external_access_token",
                new_callable=PropertyMock,
                side_effect=ValueError("No external access token found"),
            ),
        ):
            client = BitbucketClient(
                workspace="test-workspace",
                host="https://api.bitbucket.org/2.0",
                workspace_token="workspace-token",
            )
            # Should fallback to workspace token
            assert client.headers["Authorization"] == "Bearer workspace-token"

    def test_refresh_request_auth_creds_oauth(self) -> None:
        """Test refresh_request_auth_creds with OAuth enabled."""
        from httpx import Request

        with (
            patch.object(BitbucketClient, "is_oauth_enabled", return_value=True),
            patch.object(BitbucketClient, "external_access_token", "oauth-token"),
        ):
            client = BitbucketClient(
                workspace="test-workspace",
                host="https://api.bitbucket.org/2.0",
                workspace_token="test-token",
            )

            request = Request("GET", "https://example.com")
            refreshed_request = client.refresh_request_auth_creds(request)

            assert refreshed_request.headers["Authorization"] == "Bearer oauth-token"

    def test_refresh_request_auth_creds_no_oauth(self) -> None:
        """Test refresh_request_auth_creds with OAuth disabled."""
        from httpx import Request

        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            client = BitbucketClient(
                workspace="test-workspace",
                host="https://api.bitbucket.org/2.0",
                workspace_token="test-token",
            )

            original_request = Request("GET", "https://example.com")
            refreshed_request = client.refresh_request_auth_creds(original_request)

            # Should return the same request when OAuth is not enabled
            assert refreshed_request == original_request

    def test_create_from_ocean_config(self) -> None:
        """Test create_from_ocean_config class method."""
        from port_ocean.context.ocean import ocean

        with patch.object(BitbucketClient, "is_oauth_enabled", return_value=False):
            client = BitbucketClient.create_from_ocean_config()
            assert client.workspace == ocean.integration_config.get("bitbucket_workspace")
            assert client.base_url == ocean.integration_config.get("bitbucket_host_url")
