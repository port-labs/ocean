import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from aiolimiter import AsyncLimiter
import httpx

from client import CheckmarxClient, CheckmarxAuthenticationError, CheckmarxAPIError


class TestCheckmarxClient:
    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client for testing."""
        return AsyncMock()

    @pytest.fixture
    def client_with_api_key(self, mock_http_client):
        """Create client with API key authentication."""
        with patch('client.http_async_client', mock_http_client):
            with patch('client.CheckmarxClient._validate_auth_method', return_value=True):
                return CheckmarxClient(
                    base_url="https://ast.checkmarx.net",
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    api_key="test-api-key"
                )

    @pytest.fixture
    def client_with_oauth(self, mock_http_client):
        """Create client with OAuth authentication."""
        with patch('client.http_async_client', mock_http_client):
            with patch('client.CheckmarxClient._validate_auth_method', return_value=True):
                return CheckmarxClient(
                    base_url="https://ast.checkmarx.net",
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    client_id="test-client-id",
                    client_secret="test-client-secret"
                )

    def test_client_initialization_with_api_key(self, client_with_api_key):
        """Test client initialization with API key."""
        assert client_with_api_key.base_url == "https://ast.checkmarx.net"
        assert client_with_api_key.iam_url == "https://iam.checkmarx.net"
        assert client_with_api_key.tenant == "test-tenant"
        assert client_with_api_key.api_key == "test-api-key"
        assert client_with_api_key.client_id is None
        assert client_with_api_key.client_secret is None

    def test_client_initialization_with_oauth(self, client_with_oauth):
        """Test client initialization with OAuth credentials."""
        assert client_with_oauth.base_url == "https://ast.checkmarx.net"
        assert client_with_oauth.iam_url == "https://iam.checkmarx.net"
        assert client_with_oauth.tenant == "test-tenant"
        assert client_with_oauth.api_key is None
        assert client_with_oauth.client_id == "test-client-id"
        assert client_with_oauth.client_secret == "test-client-secret"


    def test_auth_url_property(self, client_with_api_key):
        """Test auth_url property generates correct URL."""
        expected_url = "https://iam.checkmarx.net/auth/realms/test-tenant/protocol/openid-connect/token"
        assert client_with_api_key.auth_url == expected_url

    def test_is_token_expired_no_token(self, client_with_api_key):
        """Test token expiry check when no token exists."""
        assert client_with_api_key.is_token_expired is True

    def test_is_token_expired_valid_token(self, client_with_api_key):
        """Test token expiry check with valid token."""
        client_with_api_key._token_expires_at = time.time() + 3600  # 1 hour from now
        assert client_with_api_key.is_token_expired is False

    def test_is_token_expired_expired_token(self, client_with_api_key):
        """Test token expiry check with expired token."""
        client_with_api_key._token_expires_at = time.time() - 3600  # 1 hour ago
        assert client_with_api_key.is_token_expired is True

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key_success(self, client_with_api_key, mock_http_client):
        """Test successful API key authentication."""
        # Mock successful authentication response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 1800
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = await client_with_api_key._authenticate_with_api_key()

        assert result["access_token"] == "test-access-token"
        assert result["refresh_token"] == "test-refresh-token"
        assert result["expires_in"] == 1800

        # Verify correct API call
        mock_http_client.post.assert_called_once_with(
            client_with_api_key.auth_url,
            data={
                "grant_type": "refresh_token",
                "client_id": "ast-app",
                "refresh_token": "test-api-key",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key_failure(self, client_with_api_key, mock_http_client):
        """Test API key authentication failure."""
        # Mock failed authentication response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with pytest.raises(CheckmarxAuthenticationError, match="API key authentication failed"):
            await client_with_api_key._authenticate_with_api_key()

    @pytest.mark.asyncio
    async def test_authenticate_with_oauth_success(self, client_with_oauth, mock_http_client):
        """Test successful OAuth authentication."""
        # Mock successful authentication response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "expires_in": 3600
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = await client_with_oauth._authenticate_with_oauth()

        assert result["access_token"] == "test-access-token"
        assert result["expires_in"] == 3600

        # Verify correct API call
        mock_http_client.post.assert_called_once_with(
            client_with_oauth.auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    @pytest.mark.asyncio
    async def test_authenticate_with_oauth_failure(self, client_with_oauth, mock_http_client):
        """Test OAuth authentication failure."""
        # Mock failed authentication response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid client credentials"
        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with pytest.raises(CheckmarxAuthenticationError, match="OAuth authentication failed"):
            await client_with_oauth._authenticate_with_oauth()

    @pytest.mark.asyncio
    async def test_refresh_access_token_api_key(self, client_with_api_key):
        """Test token refresh with API key."""
        with patch.object(client_with_api_key, '_authenticate_with_api_key') as mock_auth:
            mock_auth.return_value = {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 1800
            }

            await client_with_api_key._refresh_access_token()

            assert client_with_api_key._access_token == "new-access-token"
            assert client_with_api_key._refresh_token == "new-refresh-token"
            assert client_with_api_key._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_refresh_access_token_oauth(self, client_with_oauth):
        """Test token refresh with OAuth."""
        with patch.object(client_with_oauth, '_authenticate_with_oauth') as mock_auth:
            mock_auth.return_value = {
                "access_token": "new-access-token",
                "expires_in": 3600
            }

            await client_with_oauth._refresh_access_token()

            assert client_with_oauth._access_token == "new-access-token"
            assert client_with_oauth._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_get_access_token_refresh_when_expired(self, client_with_api_key):
        """Test that expired tokens are refreshed."""
        # Set up expired token
        client_with_api_key._access_token = "expired-token"
        client_with_api_key._token_expires_at = time.time() - 3600

        with patch.object(client_with_api_key, '_refresh_access_token') as mock_refresh:
            client_with_api_key._access_token = "new-token"

            token = await client_with_api_key._get_access_token()

            mock_refresh.assert_called_once()
            assert token == "new-token"

    @pytest.mark.asyncio
    async def test_auth_headers(self, client_with_api_key):
        """Test authentication headers generation."""
        with patch.object(client_with_api_key, '_get_access_token') as mock_get_token:
            mock_get_token.return_value = "test-token"

            headers = await client_with_api_key.auth_headers

            expected_headers = {
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            assert headers == expected_headers

    @pytest.mark.asyncio
    async def test_send_api_request_success(self, client_with_api_key, mock_http_client):
        """Test successful API request."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.request.return_value = mock_response

        with patch.object(client_with_api_key, '_get_access_token', return_value="test-token"):

            result = await client_with_api_key._send_api_request("/test-endpoint")

            assert result == {"data": "test"}
            mock_http_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_api_request_401_retry(self, client_with_api_key, mock_http_client):
        """Test API request with 401 error and retry."""
        # Mock 401 response on first call, success on second
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_response_401.text = "Unauthorized"

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"data": "success"}
        mock_response_success.raise_for_status = MagicMock()

        mock_http_client.request.side_effect = [
            httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response_401),
            mock_response_success
        ]

        with patch.object(client_with_api_key, '_get_access_token', return_value="test-token"):
            with patch.object(client_with_api_key, '_refresh_access_token') as mock_refresh:

                result = await client_with_api_key._send_api_request("/test-endpoint")

                assert result == {"data": "success"}
                mock_refresh.assert_called_once()
                assert mock_http_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_send_api_request_404_returns_empty(self, client_with_api_key, mock_http_client):
        """Test API request with 404 returns empty dict."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http_client.request.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(client_with_api_key, '_get_access_token', return_value="test-token"):

            result = await client_with_api_key._send_api_request("/test-endpoint")

            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_403_raises_error(self, client_with_api_key, mock_http_client):
        """Test API request with 403 raises CheckmarxAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_http_client.request.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_response
        )

        with patch.object(client_with_api_key, '_get_access_token', return_value="test-token"):

            with pytest.raises(CheckmarxAPIError, match="Access denied"):
                await client_with_api_key._send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_send_api_request_429_raises_error(self, client_with_api_key, mock_http_client):
        """Test API request with 429 raises CheckmarxAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_http_client.request.side_effect = httpx.HTTPStatusError(
            "Too Many Requests", request=MagicMock(), response=mock_response
        )

        with patch.object(client_with_api_key, '_get_access_token', return_value="test-token"):

            with pytest.raises(CheckmarxAPIError, match="Rate limit exceeded"):
                await client_with_api_key._send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_get_projects_single_page(self, client_with_api_key):
        """Test getting projects with single page."""
        mock_projects = [{"id": "1", "name": "Project 1"}, {"id": "2", "name": "Project 2"}]

        with patch.object(client_with_api_key, '_get_paginated_resources') as mock_paginated:
            async def mock_generator():
                yield mock_projects

            mock_paginated.return_value = mock_generator()

            results = []
            async for batch in client_with_api_key.get_projects():
                results.extend(batch)

            assert results == mock_projects
            mock_paginated.assert_called_once_with("/projects", "projects", {})

    @pytest.mark.asyncio
    async def test_get_projects_with_params(self, client_with_api_key):
        """Test getting projects with limit and offset."""
        with patch.object(client_with_api_key, '_get_paginated_resources') as mock_paginated:
            async def mock_generator():
                yield []

            mock_paginated.return_value = mock_generator()

            async for batch in client_with_api_key.get_projects(limit=50, offset=100):
                pass

            mock_paginated.assert_called_once_with("/projects", "projects", {"limit": 50, "offset": 100})

    @pytest.mark.asyncio
    async def test_get_scans_single_page(self, client_with_api_key):
        """Test getting scans with single page."""
        mock_scans = [{"id": "1", "projectId": "proj1"}, {"id": "2", "projectId": "proj1"}]

        with patch.object(client_with_api_key, '_get_paginated_resources') as mock_paginated:
            async def mock_generator():
                yield mock_scans

            mock_paginated.return_value = mock_generator()

            results = []
            async for batch in client_with_api_key.get_scans():
                results.extend(batch)

            assert results == mock_scans
            mock_paginated.assert_called_once_with("/scans", "scans", {})

    @pytest.mark.asyncio
    async def test_get_scans_with_project_filter(self, client_with_api_key):
        """Test getting scans filtered by project ID."""
        with patch.object(client_with_api_key, '_get_paginated_resources') as mock_paginated:
            async def mock_generator():
                yield []

            mock_paginated.return_value = mock_generator()

            async for batch in client_with_api_key.get_scans(project_id="proj-123"):
                pass

            mock_paginated.assert_called_once_with("/scans", "scans", {"project-id": "proj-123"})

    @pytest.mark.asyncio
    async def test_get_project_by_id(self, client_with_api_key):
        """Test getting a specific project by ID."""
        mock_project = {"id": "proj-123", "name": "Test Project"}

        with patch.object(client_with_api_key, '_send_api_request') as mock_request:
            mock_request.return_value = mock_project

            result = await client_with_api_key.get_project_by_id("proj-123")

            assert result == mock_project
            mock_request.assert_called_once_with("/projects/proj-123")

    @pytest.mark.asyncio
    async def test_get_scan_by_id(self, client_with_api_key):
        """Test getting a specific scan by ID."""
        mock_scan = {"id": "scan-456", "projectId": "proj-123"}

        with patch.object(client_with_api_key, '_send_api_request') as mock_request:
            mock_request.return_value = mock_scan

            result = await client_with_api_key.get_scan_by_id("scan-456")

            assert result == mock_scan
            mock_request.assert_called_once_with("/scans/scan-456")

    @pytest.mark.asyncio
    async def test_get_paginated_resources_multiple_pages(self, client_with_api_key):
        """Test paginated resources across multiple pages."""
        # Mock multiple pages of responses
        page1 = [{"id": f"item-{i}"} for i in range(100)]  # Full page
        page2 = [{"id": f"item-{i}"} for i in range(100, 150)]  # Partial page (50 items)

        with patch.object(client_with_api_key, '_send_api_request') as mock_request:
            mock_request.side_effect = [
                {"data": page1},
                {"data": page2}
            ]

            results = []
            async for batch in client_with_api_key._get_paginated_resources("/test", "data"):
                results.extend(batch)

            assert len(results) == 150
            assert mock_request.call_count == 2
