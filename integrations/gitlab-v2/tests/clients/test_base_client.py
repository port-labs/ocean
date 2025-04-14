from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.base_client import HTTPBaseClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "test-token",
        }
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestHTTPBaseClient:
    @pytest.fixture
    def client(self) -> HTTPBaseClient:
        """Initialize HTTPBaseClient with test configuration"""
        return HTTPBaseClient(
            "https://gitlab.example.com", "test-token", endpoint="api/v4"
        )

    async def test_send_api_request_success(self, client: HTTPBaseClient) -> None:
        """Test successful API request"""
        # Arrange
        method = "GET"
        path = "projects"
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "Test Project"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {"id": 1, "name": "Test Project"}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )
            mock_response.raise_for_status.assert_called_once()

    async def test_send_api_request_with_params(self, client: HTTPBaseClient) -> None:
        """Test API request with query parameters"""
        # Arrange
        method = "GET"
        path = "projects"
        params = {"per_page": 10, "page": 1}
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "Test Project"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path, params=params)

            # Assert
            assert result == {"id": 1, "name": "Test Project"}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=params,
                json=None,
            )

    async def test_send_api_request_with_data(self, client: HTTPBaseClient) -> None:
        """Test API request with request body data"""
        # Arrange
        method = "POST"
        path = "projects"
        data = {"name": "New Project", "description": "Test Description"}
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "New Project"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path, data=data)

            # Assert
            assert result == {"id": 1, "name": "New Project"}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=data,
            )

    async def test_send_api_request_404(self, client: HTTPBaseClient) -> None:
        """Test API request with 404 response"""
        # Arrange
        method = "GET"
        path = "projects/999"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )
            assert len(results) == 1
            assert results[0]["title"] == "Test Issue"
            mock_get_group_resource.assert_called_once_with("123", "issues", None)

    async def test_search_files_in_repos(self, client: GitLabClient) -> None:
        """Test file search in specific repositories using scope and query via _search_in_repository"""
        processed_files = [
            {"path": "test.json", "project_id": "123", "content": {"key": "value"}}
        ]
        repos = ["group/project"]
        scope = "blobs"
        query = "test.json"
        with patch.object(
            client,
            "_search_files_in_repository",
            return_value=async_mock_generator([processed_files]),
        ) as mock_search_repo:
            with patch.object(
                client.rest,
                "get_file_data",
                return_value={"content": '{"key": "value"}'},
            ):
                results = []
                async for batch in client.search_files(
                    scope, query, repositories=repos, skip_parsing=False
                ):
                    results.extend(batch)
                assert len(results) == 1
                assert results[0]["path"] == "test.json"
                assert results[0]["content"] == {"key": "value"}
                mock_search_repo.assert_called_once_with(
                    "group/project", "blobs", "path:test.json", False
                )

    async def test_search_files_in_groups(self, client: GitLabClient) -> None:
        """Test file search across all groups using scope and query"""
        mock_groups = [{"id": "1", "name": "Group1"}]
        processed_files = [
            {"path": "test.yaml", "project_id": "123", "content": {"key": "value"}}
        ]
        scope = "blobs"
        query = "test.yaml"
        with patch.object(
            client, "get_groups", return_value=async_mock_generator([mock_groups])
        ):
            with patch.object(
                client,
                "_search_files_in_group",
                return_value=async_mock_generator([processed_files]),
            ) as mock_search_group:
                with patch.object(
                    client.rest, "get_file_data", return_value={"content": "key: value"}
                ):
                    results = []
                    async for batch in client.search_files(
                        scope, query, skip_parsing=False
                    ):
                        results.extend(batch)
                    assert len(results) == 1
                    assert results[0]["path"] == "test.yaml"
                    assert results[0]["content"] == {"key": "value"}
                    mock_search_group.assert_called_once_with(
                        "1", "blobs", "path:test.yaml", False
                    )

    async def test_get_project(self, client: GitLabClient) -> None:
        """Test fetching a single project by path"""
        project_path = "group/project"
        mock_project = {
            "id": "123",
            "path_with_namespace": project_path,
            "default_branch": "main",
        }
        with patch.object(
            client.rest,
            "send_api_request",
            AsyncMock(return_value=mock_project),
        ) as mock_send_request:
            result = await client.get_project(project_path)
            assert result["id"] == "123"
            assert result["path_with_namespace"] == project_path
            mock_send_request.assert_called_once_with("GET", "projects/group%2Fproject")

    async def test_file_exists(self, client: GitLabClient) -> None:
        """Test checking if a file exists in a project"""
        project_id = "123"
        scope = "blobs"
        query = "test.txt"
        mock_response = [{"path": "test.txt"}]  # Non-empty response means exists
        with patch.object(
            client.rest,
            "send_api_request",
            AsyncMock(return_value=mock_response),
        ) as mock_send_request:
            exists = await client.file_exists(project_id, scope, query)
            assert exists is True
            mock_send_request.assert_called_once_with(
                "GET",
                "projects/123/search",
                params={"scope": "blobs", "search": "test.txt"},

    async def test_send_api_request_other_error(self, client: HTTPBaseClient) -> None:
        """Test API request with other HTTP error"""
        # Arrange
        method = "GET"
        path = "projects"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                await client.send_api_request(method, path)

            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )

    async def test_send_api_request_network_error(self, client: HTTPBaseClient) -> None:
        """Test API request with network error"""
        # Arrange
        method = "GET"
        path = "projects"

        with patch.object(
            client._client,
            "request",
            AsyncMock(side_effect=httpx.NetworkError("Connection error")),
        ) as mock_request:
            # Act & Assert
            with pytest.raises(httpx.NetworkError):
                await client.send_api_request(method, path)

            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )
