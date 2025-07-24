import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Request, Response, HTTPStatusError
from client import AikidoClient
from helpers.exceptions import MissingIntegrationCredentialException


@pytest.fixture
def aikido_client() -> AikidoClient:
    return AikidoClient(
        base_url="https://api.example.com",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )


@pytest.mark.asyncio
async def test_init_missing_credentials() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        AikidoClient(base_url="", client_id="", client_secret="")


@pytest.mark.asyncio
async def test_generate_oauth_token_success(aikido_client: AikidoClient) -> None:
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {"access_token": "test_token", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_response
        token = await aikido_client._generate_oauth_token()

        assert token == "test_token"
        assert aikido_client._access_token == "test_token"
        assert aikido_client._token_expiry > time.time()
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_oauth_token_failure(aikido_client: AikidoClient) -> None:
    request = Request("POST", "https://api.example.com/oauth/token")
    response = Response(status_code=401, request=request)

    with patch.object(
        aikido_client.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            "Error", request=request, response=response
        )
        with pytest.raises(HTTPStatusError):
            await aikido_client._generate_oauth_token()


@pytest.mark.asyncio
async def test_get_valid_token_new_token(aikido_client: AikidoClient) -> None:
    with patch.object(
        aikido_client, "_generate_oauth_token", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = "new_token"
        token = await aikido_client._get_valid_token()
        assert token == "new_token"


@pytest.mark.asyncio
async def test_get_valid_token_existing_token(aikido_client: AikidoClient) -> None:
    aikido_client._access_token = "existing_token"
    aikido_client._token_expiry = time.time() + 3600
    token = await aikido_client._get_valid_token()
    assert token == "existing_token"


@pytest.mark.asyncio
async def test_send_api_request_success(aikido_client: AikidoClient) -> None:
    test_data = {"key": "value"}
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client, "_get_valid_token", new_callable=AsyncMock
    ) as mock_token:
        with patch.object(
            aikido_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_token.return_value = "test_token"
            mock_request.return_value = mock_response

            result = await aikido_client._send_api_request("test_endpoint")

            assert result == test_data
            mock_request.assert_called_once_with(
                method="GET",
                url="https://api.example.com/test_endpoint",
                params=None,
                json=None,
                headers={
                    "Authorization": "Bearer test_token",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )


@pytest.mark.asyncio
async def test_send_api_request_404(aikido_client: AikidoClient) -> None:
    sample_req = Request("GET", "https://api.example.com/not_found")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "404", request=sample_req, response=mock_response
    )

    with patch.object(aikido_client, "_get_valid_token", new_callable=AsyncMock):
        with patch.object(
            aikido_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            result = await aikido_client._send_api_request("not_found")
            assert result == {}


@pytest.mark.asyncio
async def test_get_repositories(aikido_client: AikidoClient) -> None:
    test_repos = [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"repositories": test_repos}

        repos = []
        async for batch in aikido_client.get_repositories():
            repos.extend(batch)

        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"
        assert repos[1]["name"] == "repo2"


@pytest.mark.asyncio
async def test_get_repositories_empty(aikido_client: AikidoClient) -> None:
    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"repositories": []}

        repos = []
        async for batch in aikido_client.get_repositories():
            repos.extend(batch)

        assert len(repos) == 0


@pytest.mark.asyncio
async def test_get_all_issues(aikido_client: AikidoClient) -> None:
    test_issues = [{"id": 1, "title": "issue1"}, {"id": 2, "title": "issue2"}]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = test_issues

        issues = await aikido_client.get_all_issues()
        assert len(issues) == 2
        assert issues[0]["title"] == "issue1"
        assert issues[1]["title"] == "issue2"


@pytest.mark.asyncio
async def test_get_all_issues_empty(aikido_client: AikidoClient) -> None:
    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = []

        issues = await aikido_client.get_all_issues()
        assert len(issues) == 0


@pytest.mark.asyncio
async def test_get_repositories_pagination(aikido_client: AikidoClient) -> None:
    """Test pagination in get_repositories method"""
    first_page = [{"id": i, "name": f"repo{i}"} for i in range(1, 101)]
    second_page = [{"id": i, "name": f"repo{i}"} for i in range(101, 111)]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            {"repositories": first_page},
            {"repositories": second_page},
        ]

        all_repos = []
        async for batch in aikido_client.get_repositories():
            all_repos.extend(batch)

        assert len(all_repos) == 110
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_repositories_direct_list_response(
    aikido_client: AikidoClient,
) -> None:
    """Test get_repositories when API returns a direct list instead of wrapped in 'repositories' key"""
    test_repos = [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = test_repos

        repos = []
        async for batch in aikido_client.get_repositories():
            repos.extend(batch)

        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"


@pytest.mark.asyncio
async def test_get_repositories_exception_handling(aikido_client: AikidoClient) -> None:
    """Test exception handling in get_repositories"""
    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("API Error")

        repos = []
        async for batch in aikido_client.get_repositories():
            repos.extend(batch)

        assert len(repos) == 0


@pytest.mark.asyncio
async def test_get_all_issues_with_dict_response(aikido_client: AikidoClient) -> None:
    """Test get_all_issues when API returns dict with 'issues' key"""
    test_issues = [{"id": 1, "title": "issue1"}, {"id": 2, "title": "issue2"}]

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"issues": test_issues}

        issues = await aikido_client.get_all_issues()
        assert len(issues) == 2
        assert issues[0]["title"] == "issue1"
        mock_request.assert_called_once_with(
            "api/public/v1/issues/export", params={"format": "json"}
        )


@pytest.mark.asyncio
async def test_get_all_issues_exception_handling(aikido_client: AikidoClient) -> None:
    """Test exception handling in get_all_issues"""
    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("API Error")

        issues = await aikido_client.get_all_issues()
        assert len(issues) == 0


@pytest.mark.asyncio
async def test_get_issues_in_batches(aikido_client: AikidoClient) -> None:
    """Test get_issues_in_batches method"""
    test_issues = [{"id": i, "title": f"issue{i}"} for i in range(1, 251)]  # 250 issues

    with patch.object(
        aikido_client, "get_all_issues", new_callable=AsyncMock
    ) as mock_get_all:
        mock_get_all.return_value = test_issues

        batches = []
        async for batch in aikido_client.get_issues_in_batches(batch_size=100):
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 100
        assert len(batches[1]) == 100
        assert len(batches[2]) == 50


@pytest.mark.asyncio
async def test_get_issues_in_batches_custom_size(aikido_client: AikidoClient) -> None:
    """Test get_issues_in_batches with custom batch size"""
    test_issues = [{"id": i, "title": f"issue{i}"} for i in range(1, 21)]

    with patch.object(
        aikido_client, "get_all_issues", new_callable=AsyncMock
    ) as mock_get_all:
        mock_get_all.return_value = test_issues

        batches = []
        async for batch in aikido_client.get_issues_in_batches(batch_size=7):
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 7
        assert len(batches[1]) == 7
        assert len(batches[2]) == 6


@pytest.mark.asyncio
async def test_get_issue_detail_success(aikido_client: AikidoClient) -> None:
    """Test successful get_issue_detail"""
    test_issue = {"id": "123", "title": "Test Issue", "severity": "high"}

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = test_issue

        result = await aikido_client.get_issue_detail("123")

        assert result == test_issue
        mock_request.assert_called_once_with("issues/123", method="GET")


@pytest.mark.asyncio
async def test_get_issue_detail_exception(aikido_client: AikidoClient) -> None:
    """Test get_issue_detail exception handling"""
    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("API Error")

        result = await aikido_client.get_issue_detail("123")

        assert result == {}


@pytest.mark.asyncio
async def test_get_repository_detail_success(aikido_client: AikidoClient) -> None:
    """Test successful get_repository_detail"""
    test_repo = {"id": "456", "name": "test-repo", "language": "python"}

    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = test_repo

        result = await aikido_client.get_repository_detail("456")

        assert result == test_repo
        mock_request.assert_called_once_with(
            "api/public/v1/repositories/code/456", method="GET"
        )


@pytest.mark.asyncio
async def test_get_repository_detail_exception(aikido_client: AikidoClient) -> None:
    """Test get_repository_detail exception handling"""
    with patch.object(
        aikido_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("API Error")

        result = await aikido_client.get_repository_detail("456")

        assert result == {}


@pytest.mark.asyncio
async def test_send_api_request_with_post_method(aikido_client: AikidoClient) -> None:
    """Test _send_api_request with POST method and JSON data"""
    test_data = {"result": "success"}
    json_payload = {"key": "value"}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client, "_get_valid_token", new_callable=AsyncMock
    ) as mock_token:
        with patch.object(
            aikido_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_token.return_value = "test_token"
            mock_request.return_value = mock_response

            result = await aikido_client._send_api_request(
                "test_endpoint", method="POST", json_data=json_payload
            )

            assert result == test_data
            mock_request.assert_called_once_with(
                method="POST",
                url="https://api.example.com/test_endpoint",
                params=None,
                json=json_payload,
                headers={
                    "Authorization": "Bearer test_token",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )


@pytest.mark.asyncio
async def test_send_api_request_with_params(aikido_client: AikidoClient) -> None:
    """Test _send_api_request with query parameters"""
    test_data = {"result": "success"}
    params = {"page": 1, "per_page": 50}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client, "_get_valid_token", new_callable=AsyncMock
    ) as mock_token:
        with patch.object(
            aikido_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_token.return_value = "test_token"
            mock_request.return_value = mock_response

            result = await aikido_client._send_api_request(
                "test_endpoint", params=params
            )

            assert result == test_data
            mock_request.assert_called_once_with(
                method="GET",
                url="https://api.example.com/test_endpoint",
                params=params,
                json=None,
                headers={
                    "Authorization": "Bearer test_token",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )


@pytest.mark.asyncio
async def test_send_api_request_unexpected_exception(
    aikido_client: AikidoClient,
) -> None:
    """Test _send_api_request with unexpected exception"""
    with patch.object(aikido_client, "_get_valid_token", new_callable=AsyncMock):
        with patch.object(
            aikido_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Unexpected error")

            with pytest.raises(Exception, match="Unexpected error"):
                await aikido_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_send_api_request_non_404_http_error(aikido_client: AikidoClient) -> None:
    """Test _send_api_request with non-404 HTTP error"""
    sample_req = Request("GET", "https://api.example.com/not_found")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "500 Internal Server Error", request=sample_req, response=mock_response
    )

    with patch.object(aikido_client, "_get_valid_token", new_callable=AsyncMock):
        with patch.object(
            aikido_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(HTTPStatusError):
                await aikido_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_init_strips_trailing_slash_from_base_url() -> None:
    """Test that trailing slash is stripped from base_url during initialization"""
    client = AikidoClient(
        base_url="https://api.example.com/",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    assert client.base_url == "https://api.example.com"


@pytest.mark.asyncio
async def test_generate_oauth_token_with_custom_expires_in(
    aikido_client: AikidoClient,
) -> None:
    """Test OAuth token generation with custom expires_in value"""
    custom_expires = 7200
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": custom_expires,
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_response

        start_time = time.time()
        token = await aikido_client._generate_oauth_token()

        expected_expiry = start_time + custom_expires - 60
        assert abs(aikido_client._token_expiry - expected_expiry) < 2
        assert token == "test_token"


@pytest.mark.asyncio
async def test_get_valid_token_expired_token(aikido_client: AikidoClient) -> None:
    """Test _get_valid_token when existing token is expired"""
    aikido_client._access_token = "expired_token"
    aikido_client._token_expiry = time.time() - 100

    with patch.object(
        aikido_client, "_generate_oauth_token", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = "new_token"

        token = await aikido_client._get_valid_token()

        assert token == "new_token"
        mock_gen.assert_called_once()
