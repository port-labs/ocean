from unittest.mock import AsyncMock, MagicMock
import httpx

import pytest
from typing import Any

import asyncio


@pytest.fixture
def mock_harbor_config() -> dict[str, str]:
    """Mock Harbor configuration."""
    return {
        "harbor_url": "http://localhost:8081",
        "username": "admin",
        "password": "Harbor12345",
    }


@pytest.fixture
def mock_project_data() -> list[dict[str, Any]]:
    """Mock Harbor project data."""
    return [
        {
            "project_id": 1,
            "name": "library",
            "owner_name": "admin",
            "creation_time": "2024-01-01T00:00:00Z",
            "update_time": "2024-01-02T00:00:00Z",
            "repo_count": 5,
            "metadata": {
                "public": "true",
                "auto_scan": "true",
            },
        },
        {
            "project_id": 2,
            "name": "ocean-integration",
            "owner_name": "admin",
            "creation_time": "2024-01-03T00:00:00Z",
            "update_time": "2024-01-04T00:00:00Z",
            "repo_count": 3,
            "metadata": {
                "public": "false",
                "auto_scan": "false",
            },
        },
    ]


@pytest.fixture
def mock_user_data() -> list[dict[str, Any]]:
    """Mock Harbor user data."""
    return [
        {
            "user_id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "realname": "Admin User",
            "comment": "System administrator",
            "sysadmin_flag": True,
            "creation_time": "2024-01-01T00:00:00Z",
            "update_time": "2024-01-02T00:00:00Z",
        },
        {
            "user_id": 2,
            "username": "developer",
            "email": "dev@example.com",
            "realname": "Developer User",
            "comment": "Developer account",
            "sysadmin_flag": False,
            "creation_time": "2024-01-03T00:00:00Z",
            "update_time": "2024-01-04T00:00:00Z",
        },
    ]


@pytest.fixture
def mock_repository_data() -> list[dict[str, Any]]:
    """Mock Harbor repository data."""
    return [
        {
            "id": 1,
            "project_id": 2,
            "name": "ocean-integration/redis",
            "description": "Redis repository",
            "artifact_count": 2,
            "pull_count": 10,
            "creation_time": "2024-01-05T00:00:00Z",
            "update_time": "2024-01-06T00:00:00Z",
        },
        {
            "id": 2,
            "project_id": 2,
            "name": "ocean-integration/nginx",
            "description": "Nginx repository",
            "artifact_count": 1,
            "pull_count": 5,
            "creation_time": "2024-01-07T00:00:00Z",
            "update_time": "2024-01-08T00:00:00Z",
        },
    ]


@pytest.fixture
def mock_artifact_data() -> list[dict[str, Any]]:
    """Mock Harbor artifact data."""
    return [
        {
            "id": 1,
            "type": "IMAGE",
            "media_type": "application/vnd.docker.distribution.manifest.v2+json",
            "manifest_media_type": "application/vnd.docker.distribution.manifest.v2+json",
            "project_id": 2,
            "repository_id": 1,
            "digest": "sha256:e19a92f6821ebdbfa6676b7133c594c7ea9c3702daf773f5064845b9f8642b93",
            "size": 123456789,
            "push_time": "2024-01-09T00:00:00Z",
            "pull_time": "2024-01-10T00:00:00Z",
            "tags": [
                {
                    "id": 1,
                    "name": "v1",
                    "push_time": "2024-01-09T00:00:00Z",
                    "pull_time": "2024-01-10T00:00:00Z",
                    "immutable": False,
                }
            ],
            "labels": [],
            "scan_overview": {
                "application/vnd.security.vulnerability.report; version=1.1": {
                    "report_id": "abc123",
                    "scan_status": "Success",
                    "severity": "High",
                    "duration": 30,
                    "summary": {
                        "total": 10,
                        "fixable": 5,
                        "summary": {
                            "High": 2,
                            "Medium": 5,
                            "Low": 3,
                        },
                    },
                }
            },
        }
    ]


@pytest.fixture
def mock_webhook_artifact_pushed() -> dict[str, Any]:
    """Mock Harbor artifact pushed webhook payload."""
    return {
        "specversion": "1.0",
        "id": "4418e706-e298-4f5a-8b7e-fa842a37eb17",
        "source": "/projects/2/webhook/policies/17",
        "type": "harbor.artifact.pushed",
        "datacontenttype": "application/json",
        "time": "2025-10-30T01:06:56Z",
        "data": {
            "resources": [
                {
                    "digest": "sha256:e19a92f6821ebdbfa6676b7133c594c7ea9c3702daf773f5064845b9f8642b93",
                    "tag": "v1",
                    "resource_url": "localhost:8081/ocean-integration/redis:v1",
                }
            ],
            "repository": {
                "date_created": 1761785663,
                "name": "redis",
                "namespace": "ocean-integration",
                "repo_full_name": "ocean-integration/redis",
                "repo_type": "public",
            },
        },
        "requestid": "f713d9db-7c46-447b-b81e-07b41459113a",
        "operator": "admin",
    }


@pytest.fixture
def mock_webhook_artifact_deleted() -> dict[str, Any]:
    """Mock Harbor artifact deleted webhook payload."""
    return {
        "specversion": "1.0",
        "id": "abb172d8-cff0-4677-a8b5-338aab0e797e",
        "source": "/projects/2/webhook/policies/17",
        "type": "harbor.artifact.deleted",
        "datacontenttype": "application/json",
        "time": "2025-10-30T01:16:42Z",
        "data": {
            "resources": [
                {
                    "digest": "sha256:e19a92f6821ebdbfa6676b7133c594c7ea9c3702daf773f5064845b9f8642b93",
                    "tag": "v1",
                    "resource_url": "localhost:8081/ocean-integration/redis:v1",
                }
            ],
            "repository": {
                "date_created": 1761785663,
                "name": "redis",
                "namespace": "ocean-integration",
                "repo_full_name": "ocean-integration/redis",
                "repo_type": "public",
            },
        },
        "requestid": "c0f72b3c-395d-4e95-a914-465956c05c39",
        "operator": "admin",
    }


@pytest.fixture(autouse=True)
def mock_ocean_context(monkeypatch):
    """Mock Ocean context for cache decorator."""
    # Create fake cache provider
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=None)  # No cached data
    fake_cache.set = AsyncMock(return_value=None)

    # Create fake app
    fake_app = MagicMock()
    fake_app.cache_provider = fake_cache

    # Create fake ocean context
    fake_ocean = MagicMock()
    fake_ocean.app = fake_app
    fake_ocean._app = fake_app  # Also set _app since it checks this

    # Patch where cache decorator imports ocean from
    monkeypatch.setattr("port_ocean.utils.cache.ocean", fake_ocean)

    return fake_ocean
