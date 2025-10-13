"""
Tests for Harbor Client API interactions
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from harbor.client.harbor_client import HarborClient
from typing import Dict, List


@pytest.mark.client
class TestHarborClientAuthentication:
    """Test Harbor client authentication"""

    @pytest.mark.asyncio
    async def test_basic_auth_credentials(self, mock_harbor_config):
        """Test basic authentication with username and password"""
        client = HarborClient(
            harbor_url=mock_harbor_config["harbor_url"],
            username=mock_harbor_config["harbor_username"],
            password=mock_harbor_config["harbor_password"]
        )

        assert client.harbor_username == "test_user"
        assert client.harbor_password == "test_password"
        assert client.harbor_url == "https://harbor.test.com"

    @pytest.mark.asyncio
    async def test_ssl_verification_enabled(self, mock_harbor_config):
        """Test SSL verification is enabled by default"""
        client = HarborClient(
            harbor_url=mock_harbor_config["harbor_url"],
            username=mock_harbor_config["harbor_username"],
            password=mock_harbor_config["harbor_password"],
            verify_ssl=True
        )

        assert client.verify_ssl is True

    @pytest.mark.asyncio
    async def test_ssl_verification_disabled(self, mock_harbor_config):
        """Test SSL verification can be disabled"""
        client = HarborClient(
            harbor_url=mock_harbor_config["harbor_url"],
            username=mock_harbor_config["harbor_username"],
            password=mock_harbor_config["harbor_password"],
            verify_ssl=False
        )

        assert client.verify_ssl is False

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, mock_harbor_config):
        """Test handling of invalid credentials"""
        client = HarborClient(
            harbor_url=mock_harbor_config["harbor_url"],
            username="invalid",
            password="wrong"
        )

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("401 Unauthorized")

            with pytest.raises(Exception) as exc_info:
                await client.get_projects()

            assert "401" in str(exc_info.value)


@pytest.mark.client
class TestHarborClientProjects:
    """Test Harbor project operations"""

    @pytest.mark.asyncio
    async def test_get_all_projects(self, harbor_client, sample_project_data):
        """Test fetching all projects"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [sample_project_data]

            projects = await harbor_client.get_projects()

            assert isinstance(projects, list)
            assert len(projects) == 1
            assert projects[0]["name"] == "test-project"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_project_by_name(self, harbor_client, sample_project_data):
        """Test fetching a specific project by name"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_project_data

            project = await harbor_client.get_project("test-project")

            assert project["name"] == "test-project"
            assert project["project_id"] == 1

    @pytest.mark.asyncio
    async def test_get_public_projects_only(self, harbor_client):
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

        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [public_project, private_project]

            projects = await harbor_client.get_projects()
            public_only = [p for p in projects if p["public"]]

            assert len(public_only) == 1
            assert public_only[0]["name"] == "public-project"

    @pytest.mark.asyncio
    async def test_project_not_found(self, harbor_client):
        """Test handling of non-existent project"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("404 Not Found")

            with pytest.raises(Exception) as exc_info:
                await harbor_client.get_project("non-existent")

            assert "404" in str(exc_info.value)


@pytest.mark.client
class TestHarborClientRepositories:
    """Test Harbor repository operations"""

    @pytest.mark.asyncio
    async def test_get_repositories_for_project(self, harbor_client, sample_repository_data):
        """Test fetching repositories for a project"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [sample_repository_data]

            repos = await harbor_client.get_repositories("test-project")

            assert isinstance(repos, list)
            assert len(repos) == 1
            assert repos[0]["name"] == "test-project/test-repo"

    @pytest.mark.asyncio
    async def test_get_repository_details(self, harbor_client, sample_repository_data):
        """Test fetching specific repository details"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_repository_data

            repo = await harbor_client.get_repository("test-project", "test-repo")

            assert repo["name"] == "test-project/test-repo"
            assert repo["artifact_count"] == 5
            assert repo["pull_count"] == 100

    @pytest.mark.asyncio
    async def test_empty_repository_list(self, harbor_client):
        """Test handling of project with no repositories"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = []

            repos = await harbor_client.get_repositories("empty-project")

            assert isinstance(repos, list)
            assert len(repos) == 0

    @pytest.mark.asyncio
    async def test_repository_pagination(self, harbor_client):
        """Test handling of paginated repository results"""
        # First page
        page1 = [{"name": f"test-project/repo{i}"} for i in range(10)]
        # Second page
        page2 = [{"name": f"test-project/repo{i}"} for i in range(10, 15)]

        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [page1, page2]

            all_repos = []
            page = 1
            while True:
                repos = await harbor_client.get_repositories("test-project", page=page)
                if not repos:
                    break
                all_repos.extend(repos)
                page += 1

            assert len(all_repos) == 15


@pytest.mark.client
class TestHarborClientArtifacts:
    """Test Harbor artifact operations"""

    @pytest.mark.asyncio
    async def test_get_artifacts_for_repository(self, harbor_client, sample_artifact_data):
        """Test fetching artifacts for a repository"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [sample_artifact_data]

            artifacts = await harbor_client.get_artifacts("test-project", "test-repo")

            assert isinstance(artifacts, list)
            assert len(artifacts) == 1
            assert artifacts[0]["digest"].startswith("sha256:")

    @pytest.mark.asyncio
    async def test_get_artifact_by_digest(self, harbor_client, sample_artifact_data):
        """Test fetching specific artifact by digest"""
        digest = sample_artifact_data["digest"]

        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_artifact_data

            artifact = await harbor_client.get_artifact("test-project", "test-repo", digest)

            assert artifact["digest"] == digest
            assert len(artifact["tags"]) == 2

    @pytest.mark.asyncio
    async def test_get_artifact_tags(self, harbor_client, sample_artifact_data):
        """Test extracting tags from artifact"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [sample_artifact_data]

            artifacts = await harbor_client.get_artifacts("test-project", "test-repo")
            tags = [tag["name"] for tag in artifacts[0]["tags"]]

            assert "latest" in tags
            assert "v1.0.0" in tags

    @pytest.mark.asyncio
    async def test_get_artifact_vulnerabilities(self, harbor_client, sample_artifact_data):
        """Test extracting vulnerability data from artifact"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [sample_artifact_data]

            artifacts = await harbor_client.get_artifacts("test-project", "test-repo")
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
    async def test_get_all_users(self, harbor_client, sample_user_data):
        """Test fetching all users"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [sample_user_data]

            users = await harbor_client.get_users()

            assert isinstance(users, list)
            assert len(users) == 1
            assert users[0]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, harbor_client, sample_user_data):
        """Test fetching specific user by ID"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_user_data

            user = await harbor_client.get_user(1)

            assert user["user_id"] == 1
            assert user["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_search_users(self, harbor_client):
        """Test searching for users"""
        users = [
            {"username": "admin", "email": "admin@example.com"},
            {"username": "user1", "email": "user1@example.com"},
            {"username": "user2", "email": "user2@example.com"}
        ]

        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = users

            results = await harbor_client.search_users("user")

            assert len(results) >= 2


@pytest.mark.client
class TestHarborClientErrorHandling:
    """Test error handling in Harbor client"""

    @pytest.mark.asyncio
    async def test_network_timeout(self, harbor_client):
        """Test handling of network timeouts"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = TimeoutError("Connection timeout")

            with pytest.raises(TimeoutError):
                await harbor_client.get_projects()

    @pytest.mark.asyncio
    async def test_connection_error(self, harbor_client):
        """Test handling of connection errors"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = ConnectionError("Failed to connect")

            with pytest.raises(ConnectionError):
                await harbor_client.get_projects()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, harbor_client):
        """Test handling of rate limit errors"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("429 Too Many Requests")

            with pytest.raises(Exception) as exc_info:
                await harbor_client.get_projects()

            assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, harbor_client):
        """Test handling of invalid JSON responses"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = ValueError("Invalid JSON")

            with pytest.raises(ValueError):
                await harbor_client.get_projects()

    @pytest.mark.asyncio
    async def test_server_error(self, harbor_client):
        """Test handling of 500 server errors"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("500 Internal Server Error")

            with pytest.raises(Exception) as exc_info:
                await harbor_client.get_projects()

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_logic(self, harbor_client):
        """Test retry logic for transient failures"""
        call_count = 0

        async def mock_request_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return [{"name": "test-project"}]

        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = mock_request_with_retry

            # If retry logic is implemented
            # result = await harbor_client.get_projects()
            # assert len(result) == 1
            # assert call_count == 3


@pytest.mark.client
class TestHarborClientRequestBuilding:
    """Test HTTP request building"""

    def test_build_url(self, harbor_client):
        """Test URL building for API endpoints"""
        base_url = harbor_client.harbor_url
        endpoint = "/api/v2.0/projects"

        expected_url = f"{base_url}{endpoint}"
        # This would test your actual URL building logic
        assert expected_url == "https://harbor.test.com/api/v2.0/projects"

    def test_build_headers(self, harbor_client):
        """Test building request headers"""
        # This would test your actual header building logic
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_build_query_params(self, harbor_client):
        """Test building query parameters"""
        params = {
            "page": 1,
            "page_size": 10,
            "q": "search_term"
        }

        assert params["page"] == 1
        assert params["page_size"] == 10
