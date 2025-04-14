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
            results: list[dict[str, Any]] = []
            async for batch in client.get_groups_resource([group], "issues"):
                results.extend(batch)
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
            client, "get_project", AsyncMock(return_value=mock_project)
        ) as mock_get_project:
            with patch.object(
                client.rest,
                "get_paginated_project_resource",
                return_value=async_mock_generator([mock_tree]),
            ) as mock_get_paginated:
                # Act
                results = []
                async for batch in client.get_repository_folders(
                    path, repository, branch
                ):
                    results.extend(batch)

                # Assert
                assert len(results) == 1  # Only one folder from mock_tree
                assert results[0]["folder"]["name"] == "folder1"
                assert results[0]["repo"] == mock_project
                assert results[0]["__branch"] == "develop"

                mock_get_project.assert_called_once_with("group/project1")
                mock_get_paginated.assert_called_once_with(
                    "group/project1",
                    "repository/tree",
                    {"ref": "develop", "path": "src", "recursive": False},
                )

    async def test_get_project_jobs(self, client: GitLabClient) -> None:
        """Test fetching project jobs"""
        # Arrange
        mock_projects = [{"id": 1, "name": "Test Project"}]
        mock_jobs = [{"id": 1, "name": "Test Job"}]

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([mock_jobs]),
        ) as mock_get_paginated:
            results = []
            async for batch in client.get_project_jobs(mock_projects):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == 1
            assert results[0]["name"] == "Test Job"
            mock_get_paginated.assert_called_once_with(
                "1", "jobs", params={"per_page": 100}
            )

    async def test_project_resource(self, client: GitLabClient) -> None:
        """Test project resource fetching delegates to REST client"""
        # Arrange
        mock_pipelines = [{"id": 1, "name": "Test Pipeline"}]
        mock_projects = [{"id": 1, "name": "Test Project"}]

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([mock_pipelines]),
        ) as mock_get_project_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_projects_resource(mock_projects, "pipelines"):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["id"] == 1
            assert results[0]["name"] == "Test Pipeline"
            mock_get_project_resource.assert_called_once_with("1", "pipelines")

    async def test_process_file_with_file_reference(self, client: GitLabClient) -> None:
        """Test that parsed file content with file:// reference fetches and resolves content."""
        # Arrange
        file = {
            "path": "config.yaml",
            "project_id": "123",
            "ref": "main",
        }
        mock_file_content = """
        key: value
        ref: file://other_file.txt
        """
        mock_referenced_content = "Referenced content"
        mock_file_data = {
            "content": mock_file_content,
            "path": "config.yaml",
        }
        expected_parsed_content = {
            "key": "value",
            "ref": mock_referenced_content,
        }

        with (
            patch.object(
                client.rest,
                "get_file_data",
                AsyncMock(return_value=mock_file_data),
            ) as mock_get_file_data,
            patch.object(
                client,
                "get_file_content",
                AsyncMock(return_value=mock_referenced_content),
            ) as mock_get_file_content,
        ):
            # Act
            result = await client._process_file(
                file, context="test_context", skip_parsing=False
            )

            # Assert
            assert result["path"] == "config.yaml"
            assert result["project_id"] == "123"
            assert result["content"] == expected_parsed_content
            mock_get_file_data.assert_called_once_with("123", "config.yaml", "main")
            mock_get_file_content.assert_called_once_with(
                "123", "other_file.txt", "main"
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
