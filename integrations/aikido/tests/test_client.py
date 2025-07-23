import time
from httpx import Response, HTTPStatusError
from typing import Any, Dict, List
import pytest
from unittest.mock import MagicMock, patch
from httpx import Request
from client import AikidoClient
from helpers.exceptions import MissingIntegrationCredentialException


@pytest.mark.asyncio
async def test_get_repositories_success() -> None:
    """Test successful repository fetching."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "1", "name": "repo1"}]
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        repos: List[Dict[str, Any]] = []
        async for batch in aikido.get_repositories():
            repos.extend(batch)

        assert len(repos) == 1
        assert repos[0]["id"] == "1"


@pytest.mark.asyncio
async def test_get_repositories_empty() -> None:
    """Test empty repository response."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        repos: List[Dict[str, Any]] = []
        async for batch in aikido.get_repositories():
            repos.extend(batch)

        assert len(repos) == 0


@pytest.mark.asyncio
async def test_get_all_issues_success() -> None:
    """Test successful issues fetching."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "1", "title": "issue1"}]
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        issues = await aikido.get_all_issues()

        assert len(issues) == 1
        assert issues[0]["id"] == "1"


@pytest.mark.asyncio
async def test_get_issues_in_batches() -> None:
    """Test batch processing of issues."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": str(i)} for i in range(150)]
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        batches: List[List[Dict[str, Any]]] = []
        async for batch in aikido.get_issues_in_batches(batch_size=50):
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 50
        assert len(batches[1]) == 50
        assert len(batches[2]) == 50


@pytest.mark.asyncio
async def test_get_issue_detail_success() -> None:
    """Test successful issue detail fetching."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1", "title": "test issue"}
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        issue = await aikido.get_issue_detail("1")

        assert issue["id"] == "1"
        assert issue["title"] == "test issue"


@pytest.mark.asyncio
async def test_get_repository_detail_success() -> None:
    """Test successful repository detail fetching."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1", "name": "test repo"}
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        repo = await aikido.get_repository_detail("1")

        assert repo["id"] == "1"
        assert repo["name"] == "test repo"


@pytest.mark.asyncio
async def test_http_error_handling() -> None:
    """Test HTTP error handling."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "Not found",
            request=Request("GET", "http://test.com"),
            response=Response(404),
        )
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        repo = await aikido.get_repository_detail("1")

        assert repo == {}


def test_missing_credentials() -> None:
    """Test initialization with missing credentials."""
    with pytest.raises(MissingIntegrationCredentialException):
        AikidoClient("", "client_id", "client_secret")

    with pytest.raises(MissingIntegrationCredentialException):
        AikidoClient("http://test.com", "", "client_secret")

    with pytest.raises(MissingIntegrationCredentialException):
        AikidoClient("http://test.com", "client_id", "")


@pytest.mark.asyncio
async def test_token_generation() -> None:
    """Test OAuth token generation."""
    with patch("client.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_client.return_value.__aenter__.return_value.request.return_value = (
            mock_response
        )

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")
        token = await aikido._generate_oauth_token()

        assert token == "test_token"
        assert aikido._access_token == "test_token"
        assert aikido._token_expiry > time.time()


@pytest.mark.asyncio
async def test_token_reuse() -> None:
    """Test token reuse before expiration."""
    with patch("client.AsyncClient") as mock_client:
        # First call - generate token
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }

        # Second call - shouldn't happen as token should be reused
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }

        mock_client.return_value.__aenter__.return_value.request.side_effect = [
            mock_response1,
            mock_response2,
        ]

        aikido = AikidoClient("http://test.com", "client_id", "client_secret")

        # First call - generates token
        token1 = await aikido._get_valid_token()

        # Second call - should reuse token
        token2 = await aikido._get_valid_token()

        assert token1 == "test_token"
        assert token2 == "test_token"
        # Ensure token generation was only called once
        assert mock_client.return_value.__aenter__.return_value.request.call_count == 1
