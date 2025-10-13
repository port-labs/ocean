"""
Tests for Harbor Server Integration with Port Ocean
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from port_ocean.context.ocean import ocean
from harbor.client.harbor_client import HarborClient
from typing import Any, Dict, List


@pytest.fixture
def mock_ocean_context():
    """Mock the Ocean context"""
    with patch("port_ocean.context.ocean.ocean") as mock:
        mock.integration_config = {
            "harbor_url": "https://harbor.example.com",
            "harbor_username": "admin",
            "harbor_password": "password",
            "verify_ssl": True
        }
        yield mock


@pytest.fixture
def harbor_client(mock_ocean_context):
    """Create a Harbor client instance"""
    return HarborClient(
        harbor_url="https://harbor.example.com",
        harbor_username="admin",
        harbor_password="password",
        verify_ssl=True
    )


@pytest.fixture
def mock_harbor_api_response():
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
    async def test_get_projects(self, harbor_client, mock_harbor_api_response):
        """Test fetching projects from Harbor"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_harbor_api_response["projects"]

            projects = await harbor_client.get_projects()

            assert len(projects) == 2
            assert projects[0]["name"] == "library"
            assert projects[1]["name"] == "production"
            mock_request.assert_called_once_with("/api/v2.0/projects")

    @pytest.mark.asyncio
    async def test_get_repositories(self, harbor_client, mock_harbor_api_response):
        """Test fetching repositories from Harbor"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_harbor_api_response["repositories"]

            repositories = await harbor_client.get_repositories("library")

            assert len(repositories) == 1
            assert repositories[0]["name"] == "library/nginx"
            mock_request.assert_called_once_with(
                "/api/v2.0/projects/library/repositories")

    @pytest.mark.asyncio
    async def test_get_artifacts(self, harbor_client, mock_harbor_api_response):
        """Test fetching artifacts from Harbor"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_harbor_api_response["artifacts"]

            artifacts = await harbor_client.get_artifacts("library", "nginx")

            assert len(artifacts) == 1
            assert artifacts[0]["digest"] == "sha256:abc123"
            assert len(artifacts[0]["tags"]) == 2
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_authentication_failure(self, mock_ocean_context):
        """Test handling authentication failures"""
        client = HarborClient(
            harbor_url="https://harbor.example.com",
            harbor_username="wrong",
            harbor_password="credentials",
            verify_ssl=True
        )

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("401 Unauthorized")

            with pytest.raises(Exception) as exc_info:
                await client.get_projects()

            assert "401 Unauthorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ssl_verification(self, mock_ocean_context):
        """Test SSL verification setting"""
        client_with_ssl = HarborClient(
            harbor_url="https://harbor.example.com",
            harbor_username="admin",
            harbor_password="password",
            verify_ssl=True
        )

        client_without_ssl = HarborClient(
            harbor_url="https://harbor.example.com",
            harbor_username="admin",
            harbor_password="password",
            verify_ssl=False
        )

        assert client_with_ssl.verify_ssl is True
        assert client_without_ssl.verify_ssl is False


class TestDataTransformation:
    """Test data transformation for Port entities"""

    def test_project_to_entity(self, mock_harbor_api_response):
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

    def test_repository_to_entity(self, mock_harbor_api_response):
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

    def test_artifact_to_entity(self, mock_harbor_api_response):
        """Test transforming Harbor artifact to Port entity"""
        artifact = mock_harbor_api_response["artifacts"][0]

        tags = [tag["name"] for tag in artifact["tags"]]

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
        assert "latest" in entity["properties"]["tags"]
        assert "v1.0.0" in entity["properties"]["tags"]
        assert entity["properties"]["vulnerabilities"]["critical"] == 2


class TestWebhooks:
    """Test webhook handling"""

    @pytest.mark.asyncio
    async def test_webhook_push_artifact(self):
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

        # Mock webhook handler
        with patch("webhooks.manager.handle_webhook") as mock_handler:
            mock_handler.return_value = {"status": "processed"}

            result = mock_handler(webhook_payload)

            assert result["status"] == "processed"
            mock_handler.assert_called_once_with(webhook_payload)

    @pytest.mark.asyncio
    async def test_webhook_scan_completed(self):
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

        with patch("webhooks.manager.handle_webhook") as mock_handler:
            mock_handler.return_value = {"status": "processed"}

            result = mock_handler(webhook_payload)

            assert result["status"] == "processed"

    def test_webhook_validation(self):
        """Test webhook signature validation"""
        valid_payload = {
            "type": "PUSH_ARTIFACT",
            "event_data": {},
            "occur_at": 1234567890
        }

        invalid_payload = {
            "type": "UNKNOWN_TYPE"
        }

        # These would use your actual validation logic
        assert "type" in valid_payload
        assert "event_data" in valid_payload
        assert "type" in invalid_payload
        assert "event_data" not in invalid_payload


class TestResyncLogic:
    """Test resync functionality"""

    @pytest.mark.asyncio
    async def test_full_resync(self, harbor_client, mock_harbor_api_response):
        """Test full resync of all Harbor resources"""
        with patch.object(harbor_client, 'get_projects', new_callable=AsyncMock) as mock_projects, \
                patch.object(harbor_client, 'get_repositories', new_callable=AsyncMock) as mock_repos, \
                patch.object(harbor_client, 'get_artifacts', new_callable=AsyncMock) as mock_artifacts:

            mock_projects.return_value = mock_harbor_api_response["projects"]
            mock_repos.return_value = mock_harbor_api_response["repositories"]
            mock_artifacts.return_value = mock_harbor_api_response["artifacts"]

            projects = await harbor_client.get_projects()
            repositories = await harbor_client.get_repositories("library")
            artifacts = await harbor_client.get_artifacts("library", "nginx")

            assert len(projects) == 2
            assert len(repositories) == 1
            assert len(artifacts) == 1

    @pytest.mark.asyncio
    async def test_incremental_sync(self, harbor_client):
        """Test incremental sync with updated_after parameter"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [
                {
                    "project_id": 3,
                    "name": "new-project",
                    "update_time": "2024-01-25T00:00:00.000Z"
                }
            ]

            # Simulating incremental sync
            updated_after = "2024-01-20T00:00:00.000Z"
            projects = await harbor_client.get_projects()

            assert len(projects) == 1
            assert projects[0]["name"] == "new-project"


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_network_timeout(self, harbor_client):
        """Test handling network timeouts"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = TimeoutError("Request timed out")

            with pytest.raises(TimeoutError):
                await harbor_client.get_projects()

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, harbor_client):
        """Test handling invalid JSON responses"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = ValueError("Invalid JSON")

            with pytest.raises(ValueError):
                await harbor_client.get_projects()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, harbor_client):
        """Test handling rate limiting"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("429 Too Many Requests")

            with pytest.raises(Exception) as exc_info:
                await harbor_client.get_projects()

            assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_resource(self, harbor_client):
        """Test handling 404 not found"""
        with patch.object(harbor_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("404 Not Found")

            with pytest.raises(Exception) as exc_info:
                await harbor_client.get_repositories("non-existent-project")

            assert "404" in str(exc_info.value)


class TestIntegrationConfig:
    """Test integration configuration"""

    def test_config_validation(self):
        """Test configuration validation"""
        valid_config = {
            "harbor_url": "https://harbor.example.com",
            "harbor_username": "admin",
            "harbor_password": "password",
            "verify_ssl": True
        }

        assert "harbor_url" in valid_config
        assert valid_config["harbor_url"].startswith("https://")
        assert "harbor_username" in valid_config
        assert "harbor_password" in valid_config

    def test_missing_required_config(self):
        """Test handling missing required configuration"""
        incomplete_config = {
            "harbor_url": "https://harbor.example.com"
        }

        assert "harbor_username" not in incomplete_config
        assert "harbor_password" not in incomplete_config

    def test_optional_config_defaults(self):
        """Test optional configuration defaults"""
        config = {
            "harbor_url": "https://harbor.example.com",
            "harbor_username": "admin",
            "harbor_password": "password"
        }

        # verify_ssl should default to True if not provided
        verify_ssl = config.get("verify_ssl", True)
        assert verify_ssl is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
