import pytest
from unittest.mock import AsyncMock, MagicMock
from harbor.clients.harbor_client import HarborClient


@pytest.fixture
def mock_harbor_client():
    """Create a mock Harbor client for testing."""
    client = MagicMock(spec=HarborClient)
    client.get_projects = AsyncMock()
    client.get_users = AsyncMock()
    client.get_repositories = AsyncMock()
    client.get_artifacts = AsyncMock()
    client.get_paginated_projects = AsyncMock()
    client.get_paginated_users = AsyncMock()
    client.get_paginated_repositories = AsyncMock()
    client.get_paginated_artifacts = AsyncMock()
    return client


@pytest.fixture
def sample_project_data():
    """Sample Harbor project data for testing."""
    return [
        {
            "project_id": 1,
            "name": "library",
            "public": True,
            "owner_id": 1,
            "owner_name": "admin",
            "creation_time": "2024-01-01T00:00:00.000Z",
            "update_time": "2024-01-01T00:00:00.000Z",
            "repo_count": 0,
            "metadata": {"public": "true"}
        },
        {
            "project_id": 2,
            "name": "opensource",
            "public": True,
            "owner_id": 1,
            "owner_name": "admin",
            "creation_time": "2024-01-01T00:00:00.000Z",
            "update_time": "2024-01-01T00:00:00.000Z",
            "repo_count": 8,
            "metadata": {"public": "true"}
        }
    ]


@pytest.fixture
def sample_user_data():
    """Sample Harbor user data for testing."""
    return [
        {
            "user_id": 1,
            "username": "admin",
            "email": "admin@harbor.local",
            "realname": "Harbor Admin",
            "sysadmin_flag": True,
            "creation_time": "2024-01-01T00:00:00.000Z"
        },
        {
            "user_id": 2,
            "username": "developer",
            "email": "dev@company.com",
            "realname": "Developer User",
            "sysadmin_flag": False,
            "creation_time": "2024-01-01T00:00:00.000Z"
        }
    ]


@pytest.fixture
def sample_repository_data():
    """Sample Harbor repository data for testing."""
    return [
        {
            "id": 1,
            "name": "opensource/nginx",
            "project_id": 2,
            "artifact_count": 1,
            "pull_count": 0,
            "creation_time": "2024-01-01T00:00:00.000Z",
            "update_time": "2024-01-01T00:00:00.000Z"
        },
        {
            "id": 2,
            "name": "opensource/redis",
            "project_id": 2,
            "artifact_count": 1,
            "pull_count": 5,
            "creation_time": "2024-01-01T00:00:00.000Z",
            "update_time": "2024-01-01T00:00:00.000Z"
        }
    ]


@pytest.fixture
def sample_artifact_data():
    """Sample Harbor artifact data for testing."""
    return [
        {
            "digest": "sha256:1234567890abcdef",
            "media_type": "application/vnd.docker.distribution.manifest.v2+json",
            "manifest_media_type": "application/vnd.docker.distribution.manifest.v2+json",
            "size": 1024000,
            "type": "IMAGE",
            "push_time": "2024-01-01T00:00:00.000Z",
            "pull_time": "2024-01-01T01:00:00.000Z",
            "tags": [{"name": "latest"}],
            "scan_overview": {
                "trivy": {
                    "summary": {
                        "high": 2,
                        "medium": 5,
                        "low": 10
                    }
                }
            }
        }
    ]


@pytest.fixture
def sample_webhook_event():
    """Sample Harbor webhook event data for testing."""
    return {
        "type": "PUSH_ARTIFACT",
        "occur_at": 1640995200,
        "operator": "admin",
        "event_data": {
            "project": {
                "name": "opensource",
                "project_id": 2
            },
            "repository": {
                "name": "opensource/nginx",
                "repo_full_name": "opensource/nginx",
                "repo_type": "private"
            },
            "resources": [
                {
                    "digest": "sha256:1234567890abcdef",
                    "tag": "latest",
                    "resource_url": "localhost:8081/opensource/nginx:latest"
                }
            ]
        }
    }