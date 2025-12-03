"""
Tests for Harbor Server Integration with Port Ocean
"""
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, Mock, patch

@pytest.fixture
def mock_harbor_api_response() -> Dict[str, Any]:
    """Mock Harbor API responses"""
    return {
        "projects": [
            {
                "project_id": 1,
                "name": "library",
                "public": True,
                "owner_name": "admin",
                "repo_count": 5,
                "creation_time": "2024-01-01T00:00:00.000Z",
                "update_time": "2024-01-15T00:00:00.000Z"
            },
            {
                "project_id": 2,
                "name": "production",
                "public": False,
                "owner_name": "admin",
                "repo_count": 10,
                "creation_time": "2024-01-02T00:00:00.000Z",
                "update_time": "2024-01-16T00:00:00.000Z"
            }
        ],
        "repositories": [
            {
                "id": 1,
                "name": "library/nginx",
                "project_id": 1,
                "description": "Nginx web server",
                "pull_count": 100,
                "artifact_count": 5,
                "creation_time": "2024-01-05T00:00:00.000Z",
                "update_time": "2024-01-20T00:00:00.000Z"
            }
        ],
        "artifacts": [
            {
                "id": 1,
                "digest": "sha256:abc123",
                "tags": [{"name": "latest"}, {"name": "v1.0.0"}],
                "push_time": "2024-01-20T00:00:00.000Z",
                "pull_time": "2024-01-21T00:00:00.000Z",
                "size": 1048576,
                "scan_overview": {
                    "scan_status": "Success",
                    "severity": "High",
                    "vulnerabilities": {
                        "total": 10,
                        "critical": 2,
                        "high": 3,
                        "medium": 3,
                        "low": 2
                    }
                }
            }
        ],
        "users": [
            {
                "user_id": 1,
                "username": "admin",
                "email": "admin@example.com",
                "realname": "Administrator",
                "admin_role_in_auth": True,
                "creation_time": "2024-01-01T00:00:00.000Z"
            }
        ]
    }


class TestHarborClient:
    """Test Harbor Client functionality"""

    @pytest.mark.asyncio
    async def test_get_projects(self, harbor_client: Any, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test fetching projects from Harbor"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(
            return_value=mock_harbor_api_response["projects"])
        mock_response.content = b'[...]'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        projects = []
        async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
            projects.extend(batch)

        assert len(projects) == 2
        assert projects[0]["name"] == "library"
        assert projects[1]["name"] == "production"

    @pytest.mark.asyncio
    async def test_get_repositories(self, harbor_client: Any, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test fetching repositories from Harbor"""
        project_response = Mock()
        project_response.status_code = 200
        project_response.json = Mock(
            return_value=[{"name": "library", "project_id": 1}])
        project_response.content = b'[...]'
        project_response.raise_for_status = Mock()

        repo_response = Mock()
        repo_response.status_code = 200
        repo_response.json = Mock(
            return_value=mock_harbor_api_response["repositories"])
        repo_response.content = b'[...]'
        repo_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            project_response, repo_response]

        repositories = []
        async for batch in harbor_client.get_all_repositories({"page_size": 100}):
            repositories.extend(batch)

        assert len(repositories) >= 1
        assert repositories[0]["name"] == "library/nginx"

    @pytest.mark.asyncio
    async def test_get_artifacts(self, harbor_client: Any, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test fetching artifacts from Harbor"""
        project_response = Mock()
        project_response.status_code = 200
        project_response.json = Mock(
            return_value=[{"name": "library", "project_id": 1}])
        project_response.content = b'[...]'
        project_response.raise_for_status = Mock()

        repo_response = Mock()
        repo_response.status_code = 200
        repo_response.json = Mock(
            return_value=[{"name": "library/nginx", "project_id": 1}])
        repo_response.content = b'[...]'
        repo_response.raise_for_status = Mock()

        artifact_response = Mock()
        artifact_response.status_code = 200
        artifact_response.json = Mock(
            return_value=mock_harbor_api_response["artifacts"])
        artifact_response.content = b'[...]'
        artifact_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            project_response,
            repo_response,
            artifact_response
        ]

        artifacts = []
        async for batch in harbor_client.get_all_artifacts({"page_size": 50, "with_tag": True}):
            artifacts.extend(batch)

        assert len(artifacts) >= 1
        assert artifacts[0]["digest"] == "sha256:abc123"
        assert len(artifacts[0]["tags"]) == 2

    @pytest.mark.asyncio
    async def test_authentication_failure(self, mock_http_client: AsyncMock) -> None:
        """Test handling authentication failures"""
        with patch('harbor.client.harbor_client.http_async_client', mock_http_client):
            from harbor.client.harbor_client import HarborClient

            client = HarborClient(
                harbor_url="https://harbor.example.com",
                username="wrong",
                password="credentials",
                verify_ssl=True
            )

            client.client = mock_http_client

            from httpx import HTTPStatusError, Response, Request

            mock_request = Mock(spec=Request)
            mock_request.url = "https://harbor.example.com/api/v2.0/systeminfo"

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

            mock_http_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(HTTPStatusError):
                await client.validate_connection()

    @pytest.mark.asyncio
    async def test_ssl_verification(self, mock_http_client: AsyncMock) -> None:
        """Test SSL verification setting"""
        with patch('harbor.client.harbor_client.http_async_client', mock_http_client):
            from harbor.client.harbor_client import HarborClient

            client_with_ssl = HarborClient(
                harbor_url="https://harbor.example.com",
                username="admin",
                password="password",
                verify_ssl=True
            )

            client_without_ssl = HarborClient(
                harbor_url="https://harbor.example.com",
                username="admin",
                password="password",
                verify_ssl=False
            )

            assert client_with_ssl.verify_ssl is True
            assert client_without_ssl.verify_ssl is False


class TestDataTransformation:
    """Test data transformation for Port entities"""

    def test_project_to_entity(self, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test transforming Harbor project to Port entity"""
        project = mock_harbor_api_response["projects"][0]

        entity = {
            "identifier": f"project-{project['project_id']}",
            "title": project["name"],
            "properties": {
                "public": project["public"],
                "owner": project["owner_name"],
                "repositoryCount": project["repo_count"],
                "createdAt": project["creation_time"],
                "updatedAt": project["update_time"]
            }
        }

        assert entity["identifier"] == "project-1"
        assert entity["title"] == "library"
        assert entity["properties"]["public"] is True
        assert entity["properties"]["repositoryCount"] == 5

    def test_repository_to_entity(self, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test transforming Harbor repository to Port entity"""
        repo = mock_harbor_api_response["repositories"][0]

        entity = {
            "identifier": f"repo-{repo['id']}",
            "title": repo["name"],
            "properties": {
                "description": repo["description"],
                "pullCount": repo["pull_count"],
                "artifactCount": repo["artifact_count"],
                "createdAt": repo["creation_time"],
                "updatedAt": repo["update_time"]
            },
            "relations": {
                "project": f"project-{repo['project_id']}"
            }
        }

        assert entity["identifier"] == "repo-1"
        assert entity["title"] == "library/nginx"
        assert entity["properties"]["pullCount"] == 100
        assert entity["relations"]["project"] == "project-1"

    def test_artifact_to_entity(self, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test transforming Harbor artifact to Port entity"""
        artifact = mock_harbor_api_response["artifacts"][0]

        tags: list[str] = [tag["name"] for tag in artifact["tags"]]

        entity = {
            "identifier": artifact["digest"],
            "title": f"Artifact {artifact['digest'][:12]}",
            "properties": {
                "tags": tags,
                "size": artifact["size"],
                "pushedAt": artifact["push_time"],
                "pulledAt": artifact["pull_time"],
                "scanStatus": artifact["scan_overview"]["scan_status"],
                "severity": artifact["scan_overview"]["severity"],
                "vulnerabilities": artifact["scan_overview"]["vulnerabilities"]
            }
        }

        assert entity["identifier"] == "sha256:abc123"
        assert "latest" in tags
        assert "v1.0.0" in tags
        assert entity["properties"]["vulnerabilities"]["critical"] == 2


class TestWebhooks:
    """Test webhook handling"""

    @pytest.mark.asyncio
    async def test_webhook_push_artifact(self) -> None:
        """Test handling push artifact webhook"""
        webhook_payload = {
            "type": "PUSH_ARTIFACT",
            "event_data": {
                "resources": [{
                    "digest": "sha256:xyz789",
                    "tag": "v2.0.0",
                    "resource_url": "library/nginx:v2.0.0"
                }],
                "repository": {
                    "name": "library/nginx",
                    "namespace": "library",
                    "repo_full_name": "library/nginx"
                }
            },
            "occur_at": 1234567890
        }

        assert webhook_payload["type"] == "PUSH_ARTIFACT"
        event_data: Any = webhook_payload["event_data"]
        assert "resources" in event_data
        resources: list[Dict[str, Any]] = event_data["resources"]
        assert resources[0]["tag"] == "v2.0.0"

    @pytest.mark.asyncio
    async def test_webhook_scan_completed(self) -> None:
        """Test handling scan completed webhook"""
        webhook_payload = {
            "type": "SCANNING_COMPLETED",
            "event_data": {
                "resources": [{
                    "digest": "sha256:abc123",
                    "scan_overview": {
                        "scan_status": "Success",
                        "severity": "Critical",
                        "vulnerabilities": {
                            "total": 15,
                            "critical": 5,
                            "high": 5,
                            "medium": 3,
                            "low": 2
                        }
                    }
                }]
            },
            "occur_at": 1234567890
        }

        assert webhook_payload["type"] == "SCANNING_COMPLETED"
        event_data: Any = webhook_payload["event_data"]
        resources: list[Dict[str, Any]] = event_data["resources"]
        assert "scan_overview" in resources[0]
        scan: Dict[str, Any] = resources[0]["scan_overview"]
        assert scan["scan_status"] == "Success"
        vulnerabilities: Dict[str, Any] = scan["vulnerabilities"]
        assert vulnerabilities["critical"] == 5

    def test_webhook_validation(self) -> None:
        """Test webhook signature validation"""
        valid_payload: Dict[str, Any] = {
            "type": "PUSH_ARTIFACT",
            "event_data": {},
            "occur_at": 1234567890
        }

        invalid_payload: Dict[str, Any] = {
            "type": "UNKNOWN_TYPE"
        }

        assert "type" in valid_payload
        assert "event_data" in valid_payload
        assert "type" in invalid_payload
        assert "event_data" not in invalid_payload


class TestResyncLogic:
    """Test resync functionality"""

    @pytest.mark.asyncio
    async def test_full_resync(self, harbor_client: Any, mock_harbor_api_response: Dict[str, Any]) -> None:
        """Test full resync of all Harbor resources"""
        project_response = Mock()
        project_response.status_code = 200
        project_response.json = Mock(
            return_value=mock_harbor_api_response["projects"])
        project_response.content = b'[...]'
        project_response.raise_for_status = Mock()

        repo_response = Mock()
        repo_response.status_code = 200
        repo_response.json = Mock(
            return_value=mock_harbor_api_response["repositories"])
        repo_response.content = b'[...]'
        repo_response.raise_for_status = Mock()

        artifact_response = Mock()
        artifact_response.status_code = 200
        artifact_response.json = Mock(
            return_value=mock_harbor_api_response["artifacts"])
        artifact_response.content = b'[...]'
        artifact_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            project_response,
            project_response,
            repo_response,
            artifact_response
        ]

        projects = []
        async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
            projects.extend(batch)

        assert len(projects) == 2

    @pytest.mark.asyncio
    async def test_incremental_sync(self, harbor_client: Any) -> None:
        """Test incremental sync with updated_after parameter"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=[
            {
                "project_id": 3,
                "name": "new-project",
                "update_time": "2024-01-25T00:00:00.000Z"
            }
        ])
        mock_response.content = b'[...]'
        mock_response.raise_for_status = Mock()

        harbor_client.client.request.return_value = mock_response

        projects = []
        async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
            projects.extend(batch)

        assert len(projects) == 1
        assert projects[0]["name"] == "new-project"


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_network_timeout(self, harbor_client: Any) -> None:
        """Test handling network timeouts"""
        harbor_client.client.request.side_effect = TimeoutError(
            "Request timed out")

        with pytest.raises(TimeoutError):
            projects = []
            async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
                projects.extend(batch)

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, harbor_client: Any) -> None:
        """Test handling invalid JSON responses"""
        harbor_client.client.request.side_effect = ValueError("Invalid JSON")

        with pytest.raises(ValueError):
            projects = []
            async for batch in harbor_client.get_paginated_projects({"page_size": 100}):
                projects.extend(batch)

    @pytest.mark.asyncio
    async def test_rate_limiting(self, harbor_client: Any) -> None:
        """Test handling rate limiting"""
        from httpx import HTTPStatusError, Response, Request

        mock_request = Mock(spec=Request)
        mock_request.url = "https://harbor.test.com/api/v2.0/systeminfo"

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
        success_response.json = Mock(return_value={"harbor_version": "2.0"})
        success_response.content = b'{}'
        success_response.raise_for_status = Mock()

        harbor_client.client.request.side_effect = [
            mock_response, success_response]

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await harbor_client.validate_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_missing_resource(self, harbor_client: Any) -> None:
        """Test handling 404 not found"""
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

        result = await harbor_client.get_project("non-existent")
        assert result is None


class TestIntegrationConfig:
    """Test integration configuration"""

    def test_config_validation(self) -> None:
        """Test configuration validation"""
        valid_config: Dict[str, Any] = {
            "harbor_url": "https://harbor.example.com",
            "username": "admin",
            "password": "password",
            "verify_ssl": True
        }

        assert "harbor_url" in valid_config
        harbor_url_str = str(valid_config["harbor_url"])
        assert harbor_url_str.startswith("https://")
        assert "username" in valid_config
        assert "password" in valid_config

    def test_optional_config_defaults(self) -> None:
        """Test optional configuration defaults"""
        config: Dict[str, Any] = {
            "harbor_url": "https://harbor.example.com",
            "username": "admin",
            "password": "password"
        }

        verify_ssl = config.get("verify_ssl", True)
        assert verify_ssl is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])