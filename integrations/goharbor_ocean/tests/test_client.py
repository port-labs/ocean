from unittest.mock import patch, AsyncMock, Mock
import asyncio
import pytest
from httpx import Response, Request, HTTPStatusError

from harbor.client import HarborClient
from harbor.exceptions import HarborAPIError, ServerError, UnauthorizedError, ForbiddenError, NotFoundError, InvalidConfigurationError, MissingCredentialsError, RateLimitError


@pytest.fixture
def harbor_config():
    return {
        'base_url': 'https://harbor.onmypc.com',
        'username': 'robot$test_robot',
        'password': 'securepassword',
    }

@pytest.fixture
def harbor_client(harbor_config):
    return HarborClient(
        base_url=harbor_config['base_url'],
        username=harbor_config['username'],
        password=harbor_config['password'],
        verify_ssl=False  # For testing purposes; in production, this should be True
    )

@pytest.fixture
def mock_async_client():
    """Mocked project API response"""

    return [
        {
            'project_id': 1,
            'name': 'test_project',
            "owner_name": "admin",
            "creation_time": "2024-01-01T00:00:00Z",
            "update_time": "2024-01-01T00:00:00Z",
            "repo_count": 5,
            "metadata": {"public": "true"}
        }
    ]

@pytest.fixture
def mock_user_response():
    return [
        {
            "user_id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "realname": "Admin User",
            "admin_role_in_auth": True,
            "creation_time": "2024-01-01T00:00:00Z",
        }
    ]


@pytest.fixture
def mock_repository_response():
    return [
        {
            "name": "library/test_nginx_repo",
            "project_id": 1,
            "description": "Test Nginx Repository",
            "pull_count": 10,
            "star_count": 2,
            "tags_count": 3,
            "update_time": "2024-01-01T00:00:00Z",
        }
    ]

@pytest.fixture
def mock_artifact_response():
    return [
        {
            "id": 1,
            "type": "IMAGE",
            "digest": "sha256:abc123",
            "size": 12345678,
            "push_time": "2024-01-01T00:00:00Z",
            "pull_time": "2024-01-01T00:00:00Z",
            "tags": [{"name": "latest"}],
        }
    ]

class TestHarborClientSetup:

    def test_client_initialization(self, harbor_config):
        client = HarborClient(**harbor_config, verify_ssl=False)
        assert client.base_url == harbor_config['base_url']
        assert client.username == harbor_config['username']
        assert client.password == harbor_config['password']
        assert client.verify_ssl is False

        assert client.client is not None
        assert client._semaphore is not None

    def test_init_strips_trailing_slash_base_url(self, harbor_config):
        harbor_config['base_url'] = 'https://harbor.onmypc.com/'
        client = HarborClient(
            **harbor_config,
            verify_ssl=False
        )
        assert client.base_url == 'https://harbor.onmypc.com'

    def test_init_raises_invalid_configuration_error(self):
        with pytest.raises(InvalidConfigurationError):
            HarborClient(base_url='', username='user', password='pass')

        with pytest.raises(MissingCredentialsError):
            HarborClient(base_url='https://harbor.onmypc.com', username='', password='pass')

        with pytest.raises(MissingCredentialsError):
            HarborClient(base_url='https://harbor.onmypc.com', username='user', password='')

        with pytest.raises(MissingCredentialsError):
            HarborClient(base_url='https://harbor.onmypc.com', username=None, password='pass')
