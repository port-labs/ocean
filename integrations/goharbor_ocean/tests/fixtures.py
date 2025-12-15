import pytest
from httpx import HTTPStatusError, Request
from unittest.mock import AsyncMock, Mock, patch
from harbor.client import HarborClient

@pytest.fixture
def harbor_config():
    return {
        'base_url': 'https://harbor.onmypc.com',
        'username': 'robot$sampleproject+test_robot',
        'password': 'securepassword',
    }

@pytest.fixture
def harbor_client(harbor_config):
    """ for init """
    return HarborClient(
        base_url=harbor_config['base_url'],
        username=harbor_config['username'],
        password=harbor_config['password'],
        verify_ssl=False  # For testing purposes; in production, this should be True
    )


@pytest.fixture
def mock_project_response():
    return [
        {
            "project_id": 1,
            "name": "library",
            "owner_id": 1,
            "owner_name": "admin",
            "repo_count": 0,
            "creation_time": "2025-10-08T08:20:09.566Z",
            "update_time": "2025-10-08T08:20:09.566Z",
            "deleted": False,
            "metadata": {"public": "true"},
            "cve_allowlist": {
                "id": 1,
                "project_id": 1,
                "items": [],
                "creation_time": "0001-01-01T00:00:00.000Z",
                "update_time": "0001-01-01T00:00:00.000Z",
            },
        }
    ]


@pytest.fixture
def mock_repository_response():
    return [
        {
            "id": 1,
            "name": "sampleproject/alpine",
            "project_id": 2,
            "artifact_count": 1,
            "pull_count": 0,
            "creation_time": "2025-10-11T19:15:35.253Z",
            "update_time": "2025-10-11T19:15:35.253Z",
        }
    ]


@pytest.fixture
def mock_artifact_response():
    return [
        {
            "id": 1,
            "type": "IMAGE",
            "media_type": "application/vnd.docker.distribution.manifest.v2+json",
            "manifest_media_type": "application/vnd.docker.distribution.manifest.v2+json",
            "project_id": 2,
            "repository_id": 1,
            "digest": "sha256:9d04ae17046f42ec0cd37d0429fff0edd799d7159242938cc5a964dcd38c1b64",
            "size": 7342133,
            "push_time": "2025-10-11T19:15:35.439Z",
            "pull_time": "2025-10-11T19:15:35.439Z",
            "tags": [
                {
                    "id": 1,
                    "repository_id": 1,
                    "artifact_id": 1,
                    "name": "latest",
                    "push_time": "2025-10-11T19:15:35.514Z",
                    "pull_time": "0001-01-01T00:00:00.000Z",
                    "immutable": False,
                }
            ],
        }
    ]


@pytest.fixture
def mock_user_response():
    return [
        {
            "user_id": 1,
            "username": "admin",
            "email": "admin@harbor.local",
            "realname": "Harbor Admin",
            "comment": "System administrator",
            "sysadmin_flag": True,
            "admin_role_in_auth": False,
            "creation_time": "2025-10-08T08:20:09.000Z",
            "update_time": "2025-10-11T12:00:00.000Z",
        }
    ]

@pytest.fixture
def mock_http_error():
    """simple fixture factory to mock HTTP errors"""

    def _error_response(status_code, message='Error'):
        mock_request = Mock(spec=Request)
        mock_response = Mock()

        mock_response.status_code = status_code
        mock_response.headers = {}

        return HTTPStatusError(message, request=mock_request, response=mock_response)
    return _error_response


@pytest.fixture
def mock_http_response():
    """ factory to create mock httpx.Response objects """

    def _response(status_code=200, json_data=None, headers=None):
        response = Mock()

        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.headers = headers or {}

        response.raise_for_status = Mock()

        return response
    return _response

@pytest.fixture
def mock_async_client():
    # you know what this is, port_ocean.client baby
    client = AsyncMock()
    client.request = AsyncMock()
    client.timeout = Mock()
    client.auth = None
    client.headers = {}
    return client



@pytest.fixture
def harbor_client_mocked(harbor_config, mock_async_client):
    """ client with mocked Ocean HTTP client - for api method testing"""

    with patch('harbor.client.http_async_client', mock_async_client):
        client = HarborClient(
            base_url=harbor_config['base_url'],
            username=harbor_config['username'],
            password=harbor_config['password'],
            verify_ssl=False  # For testing purposes; in production, this should be True
        )
        return client
