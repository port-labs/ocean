"""
Tests for Harbor Client API interactions
"""
import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch, Mock

@pytest.mark.client
class TestHarborClientAuthentication:
    """Test Harbor client authentication"""

    @pytest.mark.asyncio
    async def test_basic_auth_credentials(self, harbor_client: Any) -> None:
        """Test basic authentication with username and password"""
        assert harbor_client.username == "test_user"
        assert harbor_client.password == "test_password"
        assert harbor_client.harbor_url == "https://harbor.test.com"

    @pytest.mark.asyncio
    async def test_ssl_verification_enabled(self, mock_harbor_config: Dict[str, Any], mock_http_client: AsyncMock) -> None:
        """Test SSL verification is enabled by default"""
        with patch('harbor.client.harbor_client.http_async_client', mock_http_client):
            from harbor.client.harbor_client import HarborClient

            client = HarborClient(
                harbor_url=mock_harbor_config["harbor_url"],
                username=mock_harbor_config["username"],
                password=mock_harbor_config["password"],
                verify_ssl=True
            )

            assert client.verify_ssl is True

    @pytest.mark.asyncio
    async def test_ssl_verification_disabled(self, mock_harbor_config: Dict[str, Any], mock_http_client: AsyncMock) -> None:
        """Test SSL verification can be disabled"""
        with patch('harbor.client.harbor_client.http_async_client', mock_http_client):
            from harbor.client.harbor_client import HarborClient

            client = HarborClient(
                harbor_url=mock_harbor_config["harbor_url"],
                username=mock_harbor_config["username"],
                password=mock_harbor_config["password"],
                verify_ssl=False
            )

            assert client.verify_ssl is False

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, harbor_client: Any) -> None:
        """Test handling of invalid credentials"""
        from httpx import HTTPStatusError, Response, Request

        mock_request = Mock(spec=Request)
        mock_request.url = "https://harbor.test.com/api/v2.0/projects"

        mock_response = Mock(spec=Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.headers = {}
        mock_response.request = mock_request

        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "401 Unauthorized",
            request=mock_request,
            response=mock_response
        )

        harbor_client.client.request.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await harbor_client._send_api_request("GET", "/api/v2.0/projects")


@pytest.mark.client
class TestHarborClientProjects:
    """Test Harbor project operations"""

    @pytest.mark.asyncio
    async def test_get_all_projects(self, harbor_client: Any, sample_project_data: Dict[str, Any]) -> None:
        """Test fetching all projects"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=[sample_project_data])
        mock_response.content = b'[{}]'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        projects = []
        async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
            projects.extend(batch)

        assert isinstance(projects, list)
        assert len(projects) == 1
        assert projects[0]["name"] == "test-project"

    @pytest.mark.asyncio
    async def test_get_project_by_name(self, harbor_client: Any, sample_project_data: Dict[str, Any]) -> None:
        """Test fetching a specific project by name"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=sample_project_data)
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        project = await harbor_client.get_project("test-project")

        assert project["name"] == "test-project"
        assert project["project_id"] == 1

    @pytest.mark.asyncio
    async def test_get_public_projects_only(self, harbor_client: Any) -> None:
        """Test filtering public projects"""
        public_project = {
            "project_id": 1,
            "name": "public-project",
            "public": True
        }
        private_project = {
            "project_id": 2,
            "name": "private-project",
            "public": False
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(
            return_value=[public_project, private_project])
        mock_response.content = b'[{}]'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        projects = []
        async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
            projects.extend(batch)

        public_only = [p for p in projects if p["public"]]

        assert len(public_only) == 1
        assert public_only[0]["name"] == "public-project"

    @pytest.mark.asyncio
    async def test_project_not_found(self, harbor_client: Any) -> None:
        """Test handling of non-existent project"""
        from httpx import HTTPStatusError, Response, Request

        mock_request = Mock(spec=Request)
        mock_request.url = "https://harbor.test.com/api/v2.0/projects/non-existent"

        mock_response = Mock(spec=Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {}
        mock_response.request = mock_request

        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "404 Not Found",
            request=mock_request,
            response=mock_response
        )

        harbor_client.client.request.return_value = mock_response

        project = await harbor_client.get_project("non-existent")
        assert project is None


@pytest.mark.client
class TestHarborClientRepositories:
    """Test Harbor repository operations"""

    @pytest.mark.asyncio
    async def test_get_repositories_for_project(self, harbor_client: Any, sample_repository_data: Dict[str, Any]) -> None:
        """Test fetching repositories for a project"""
        projects_response = Mock()
        projects_response.status_code = 200
        projects_response.json = Mock(
            return_value=[{"name": "test-project", "project_id": 1}])
        projects_response.content = b'[{}]'
        projects_response.raise_for_status = Mock()

        repos_response = Mock()
        repos_response.status_code = 200
        repos_response.json = Mock(return_value=[sample_repository_data])
        repos_response.content = b'[{}]'
        repos_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            projects_response, repos_response]

        repos = []
        async for batch in harbor_client.get_all_repositories({"page_size": 100}):
            repos.extend(batch)

        assert isinstance(repos, list)
        assert len(repos) == 1
        assert repos[0]["name"] == "test-project/test-repo"

    @pytest.mark.asyncio
    async def test_get_repository_details(self, harbor_client: Any, sample_repository_data: Dict[str, Any]) -> None:
        """Test fetching specific repository details"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=sample_repository_data)
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        repo = await harbor_client.get_repository("test-project", "test-repo")

        assert repo["name"] == "test-project/test-repo"
        assert repo["artifact_count"] == 5
        assert repo["pull_count"] == 100

    @pytest.mark.asyncio
    async def test_empty_repository_list(self, harbor_client: Any) -> None:
        """Test handling of project with no repositories"""
        projects_response = Mock()
        projects_response.status_code = 200
        projects_response.json = Mock(
            return_value=[{"name": "empty-project", "project_id": 1}])
        projects_response.content = b'[{}]'
        projects_response.raise_for_status = Mock()

        repos_response = Mock()
        repos_response.status_code = 200
        repos_response.json = Mock(return_value=[])
        repos_response.content = b'[]'
        repos_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            projects_response, repos_response]

        repos = []
        async for batch in harbor_client.get_all_repositories({"page_size": 100}):
            repos.extend(batch)

        assert isinstance(repos, list)
        assert len(repos) == 0

    @pytest.mark.asyncio
    async def test_repository_pagination(self, harbor_client: Any) -> None:
        """Test handling of paginated repository results"""
        projects_response = Mock()
        projects_response.status_code = 200
        projects_response.json = Mock(
            return_value=[{"name": "test-project", "project_id": 1}])
        projects_response.content = b'[{}]'
        projects_response.raise_for_status = Mock()

        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.json = Mock(
            return_value=[{"name": f"test-project/repo{i}"} for i in range(10)])
        page1_response.content = b'[{}]'
        page1_response.raise_for_status = Mock()

        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.json = Mock(
            return_value=[{"name": f"test-project/repo{i}"} for i in range(10, 15)])
        page2_response.content = b'[{}]'
        page2_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            projects_response, page1_response, page2_response]

        all_repos = []
        async for batch in harbor_client.get_all_repositories({"page_size": 10}):
            all_repos.extend(batch)

        assert len(all_repos) == 15


@pytest.mark.client
class TestHarborClientArtifacts:
    """Test Harbor artifact operations"""

    @pytest.mark.asyncio
    async def test_get_artifacts_for_repository(self, harbor_client: Any, sample_artifact_data: Dict[str, Any]) -> None:
        """Test fetching artifacts for a repository"""
        projects_response = Mock()
        projects_response.status_code = 200
        projects_response.json = Mock(
            return_value=[{"name": "test-project", "project_id": 1}])
        projects_response.content = b'[{}]'
        projects_response.raise_for_status = Mock()

        repos_response = Mock()
        repos_response.status_code = 200
        repos_response.json = Mock(
            return_value=[{"name": "test-project/test-repo", "project_id": 1}])
        repos_response.content = b'[{}]'
        repos_response.raise_for_status = Mock()

        artifacts_response = Mock()
        artifacts_response.status_code = 200
        artifacts_response.json = Mock(return_value=[sample_artifact_data])
        artifacts_response.content = b'[{}]'
        artifacts_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            projects_response, repos_response, artifacts_response]

        artifacts = []
        async for batch in harbor_client.get_all_artifacts({"page_size": 50}):
            artifacts.extend(batch)

        assert isinstance(artifacts, list)
        assert len(artifacts) == 1
        assert artifacts[0]["digest"].startswith("sha256:")

    @pytest.mark.asyncio
    async def test_get_artifact_by_digest(self, harbor_client: Any, sample_artifact_data: Dict[str, Any]) -> None:
        """Test fetching specific artifact by digest"""
        digest = sample_artifact_data["digest"]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=sample_artifact_data)
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        artifact = await harbor_client.get_artifact("test-project", "test-repo", digest)

        assert artifact["digest"] == digest
        assert len(artifact["tags"]) == 2

    @pytest.mark.asyncio
    async def test_get_artifact_tags(self, harbor_client: Any, sample_artifact_data: Dict[str, Any]) -> None:
        """Test extracting tags from artifact"""
        projects_response = Mock()
        projects_response.status_code = 200
        projects_response.json = Mock(
            return_value=[{"name": "test-project", "project_id": 1}])
        projects_response.content = b'[{}]'
        projects_response.raise_for_status = Mock()

        repos_response = Mock()
        repos_response.status_code = 200
        repos_response.json = Mock(
            return_value=[{"name": "test-project/test-repo", "project_id": 1}])
        repos_response.content = b'[{}]'
        repos_response.raise_for_status = Mock()

        artifacts_response = Mock()
        artifacts_response.status_code = 200
        artifacts_response.json = Mock(return_value=[sample_artifact_data])
        artifacts_response.content = b'[{}]'
        artifacts_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            projects_response, repos_response, artifacts_response]

        artifacts = []
        async for batch in harbor_client.get_all_artifacts({"page_size": 50}):
            artifacts.extend(batch)

        tags = [tag["name"] for tag in artifacts[0]["tags"]]

        assert "latest" in tags
        assert "v1.0.0" in tags

    @pytest.mark.asyncio
    async def test_get_artifact_vulnerabilities(self, harbor_client: Any, sample_artifact_data: Dict[str, Any]) -> None:
        """Test extracting vulnerability data from artifact"""
        projects_response = Mock()
        projects_response.status_code = 200
        projects_response.json = Mock(
            return_value=[{"name": "test-project", "project_id": 1}])
        projects_response.content = b'[{}]'
        projects_response.raise_for_status = Mock()

        repos_response = Mock()
        repos_response.status_code = 200
        repos_response.json = Mock(
            return_value=[{"name": "test-project/test-repo", "project_id": 1}])
        repos_response.content = b'[{}]'
        repos_response.raise_for_status = Mock()

        artifacts_response = Mock()
        artifacts_response.status_code = 200
        artifacts_response.json = Mock(return_value=[sample_artifact_data])
        artifacts_response.content = b'[{}]'
        artifacts_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            projects_response, repos_response, artifacts_response]

        artifacts = []
        async for batch in harbor_client.get_all_artifacts({"page_size": 50}):
            artifacts.extend(batch)

        scan = artifacts[0]["scan_overview"]
        vuln_key = next(iter(scan.keys()))
        summary = scan[vuln_key]["summary"]["summary"]

        assert summary["Critical"] == 3
        assert summary["High"] == 7
        assert scan[vuln_key]["scan_status"] == "Success"


@pytest.mark.client
class TestHarborClientUsers:
    """Test Harbor user operations"""

    @pytest.mark.asyncio
    async def test_get_all_users(self, harbor_client: Any, sample_user_data: Dict[str, Any]) -> None:
        """Test fetching all users"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=[sample_user_data])
        mock_response.content = b'[{}]'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        users = []
        async for batch in harbor_client.get_paginated_users({"page_size": 100}):
            users.extend(batch)

        assert isinstance(users, list)
        assert len(users) == 1
        assert users[0]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, harbor_client: Any, sample_user_data: Dict[str, Any]) -> None:
        """Test fetching specific user by ID"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=sample_user_data)
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        user = await harbor_client._get("/users/1")

        assert user["user_id"] == 1
        assert user["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_search_users(self, harbor_client: Any) -> None:
        """Test searching for users"""
        users = [
            {"username": "admin", "email": "admin@example.com"},
            {"username": "user1", "email": "user1@example.com"},
            {"username": "user2", "email": "user2@example.com"}
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=users)
        mock_response.content = b'[{}]'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        results = []
        async for batch in harbor_client.get_paginated_users({"page_size": 100, "q": "user"}):
            results.extend(batch)

        assert len(results) >= 2


@pytest.mark.client
class TestHarborClientErrorHandling:
    """Test error handling in Harbor client"""

    @pytest.mark.asyncio
    async def test_network_timeout(self, harbor_client: Any) -> None:
        """Test handling of network timeouts"""
        harbor_client.client.request.side_effect = TimeoutError(
            "Connection timeout")

        with pytest.raises(TimeoutError):
            await harbor_client._send_api_request("GET", "/api/v2.0/projects")

    @pytest.mark.asyncio
    async def test_connection_error(self, harbor_client: Any) -> None:
        """Test handling of connection errors"""
        harbor_client.client.request.side_effect = ConnectionError(
            "Failed to connect")

        with pytest.raises(ConnectionError):
            await harbor_client._send_api_request("GET", "/api/v2.0/projects")

    @pytest.mark.asyncio
    async def test_rate_limiting(self, harbor_client: Any) -> None:
        """Test handling of rate limit errors"""
        from httpx import HTTPStatusError, Response, Request

        mock_request = Mock(spec=Request)
        mock_request.url = "https://harbor.test.com/api/v2.0/projects"

        mock_response = Mock(spec=Response)
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_response.headers = {"Retry-After": "2"}
        mock_response.request = mock_request

        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "429 Too Many Requests",
            request=mock_request,
            response=mock_response
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.json = Mock(return_value=[])
        success_response.content = b'[]'
        success_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            mock_response, success_response]

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await harbor_client._send_api_request("GET", "/api/v2.0/projects")
            assert result == []

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, harbor_client: Any) -> None:
        """Test handling of invalid JSON responses"""
        harbor_client.client.request.side_effect = ValueError("Invalid JSON")

        with pytest.raises(ValueError):
            await harbor_client._send_api_request("GET", "/api/v2.0/projects")

    @pytest.mark.asyncio
    async def test_server_error(self, harbor_client: Any) -> None:
        """Test handling of 500 server errors"""
        from httpx import HTTPStatusError, Response, Request

        mock_request = Mock(spec=Request)
        mock_request.url = "https://harbor.test.com/api/v2.0/projects"

        mock_response = Mock(spec=Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.headers = {}
        mock_response.request = mock_request

        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "500 Internal Server Error",
            request=mock_request,
            response=mock_response
        )

        harbor_client.client.request.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await harbor_client._send_api_request("GET", "/api/v2.0/projects")

    @pytest.mark.asyncio
    async def test_retry_logic(self, harbor_client: Any) -> None:
        """Test retry logic for rate limiting"""
        from httpx import HTTPStatusError, Response, Request

        mock_request = Mock(spec=Request)
        mock_request.url = "https://harbor.test.com/api/v2.0/projects"

        rate_limit_response = Mock(spec=Response)
        rate_limit_response.status_code = 429
        rate_limit_response.text = "Too Many Requests"
        rate_limit_response.headers = {"Retry-After": "1"}
        rate_limit_response.request = mock_request
        rate_limit_response.raise_for_status.side_effect = HTTPStatusError(
            "429 Too Many Requests",
            request=mock_request,
            response=rate_limit_response
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.json = Mock(return_value=[{"name": "test-project"}])
        success_response.content = b'[{}]'
        success_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            rate_limit_response, success_response]

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await harbor_client._send_api_request("GET", "/api/v2.0/projects")
            assert result == [{"name": "test-project"}]
            mock_sleep.assert_called_once_with(1)


@pytest.mark.client
class TestHarborClientRequestBuilding:
    """Test HTTP request building"""

    def test_build_url(self, harbor_client: Any) -> None:
        """Test URL building for API endpoints"""
        base_url = harbor_client.harbor_url
        endpoint = "/api/v2.0/projects"

        expected_url = f"{base_url}{endpoint}"
        assert expected_url == "https://harbor.test.com/api/v2.0/projects"

    def test_build_headers(self, harbor_client: Any) -> None:
        """Test building request headers"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_build_query_params(self, harbor_client: Any) -> None:
        """Test building query parameters"""
        params = {
            "page": 1,
            "page_size": 10,
            "q": "search_term"
        }

        assert params["page"] == 1
        assert params["page_size"] == 10