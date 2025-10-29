"""
Pytest configuration and shared fixtures for Harbor integration tests
"""
import pytest
import asyncio
from typing import Generator, Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch, Mock


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_harbor_config() -> Dict[str, Any]:
    """Provide mock Harbor configuration"""
    return {
        "harbor_url": "https://harbor.test.com",
        "username": "test_user",
        "password": "test_password",
        "verify_ssl": True,
        "api_version": "v2.0"
    }


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Mock HTTP client that mimics httpx.AsyncClient"""
    client = AsyncMock()
    client.request = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.close = AsyncMock()

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={})
    mock_response.content = b'{}'
    mock_response.text = '{}'
    mock_response.headers = {}
    mock_response.raise_for_status = Mock()

    client.request.return_value = mock_response
    client.get.return_value = mock_response
    client.post.return_value = mock_response
    client.put.return_value = mock_response
    client.delete.return_value = mock_response

    return client


@pytest.fixture
def harbor_client(mock_http_client: AsyncMock) -> Generator[Any, None, None]:
    """Create a Harbor client instance with mocked HTTP client"""
    with patch('harbor.client.harbor_client.http_async_client', mock_http_client):
        from harbor.client.harbor_client import HarborClient

        client = HarborClient(
            harbor_url="https://harbor.test.com",
            username="test_user",
            password="test_password",
            verify_ssl=True
        )

        client.client = mock_http_client

        yield client


@pytest.fixture
def sample_project_data() -> Dict[str, Any]:
    """Sample Harbor project data"""
    return {
        "project_id": 1,
        "name": "test-project",
        "public": False,
        "owner_name": "admin",
        "owner_id": 1,
        "repo_count": 3,
        "chart_count": 0,
        "metadata": {
            "public": "false",
            "enable_content_trust": "false",
            "prevent_vul": "false",
            "severity": "low",
            "auto_scan": "true"
        },
        "creation_time": "2024-01-01T00:00:00.000Z",
        "update_time": "2024-01-15T12:00:00.000Z"
    }


@pytest.fixture
def sample_repository_data() -> Dict[str, Any]:
    """Sample Harbor repository data"""
    return {
        "id": 1,
        "project_id": 1,
        "name": "test-project/test-repo",
        "description": "Test repository",
        "artifact_count": 5,
        "pull_count": 100,
        "creation_time": "2024-01-05T00:00:00.000Z",
        "update_time": "2024-01-20T12:00:00.000Z"
    }


@pytest.fixture
def sample_artifact_data() -> Dict[str, Any]:
    """Sample Harbor artifact data"""
    return {
        "id": 1,
        "type": "IMAGE",
        "media_type": "application/vnd.docker.distribution.manifest.v2+json",
        "manifest_media_type": "application/vnd.docker.distribution.manifest.v2+json",
        "project_id": 1,
        "repository_id": 1,
        "digest": "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "size": 2048576,
        "icon": "sha256:0000000000000000",
        "push_time": "2024-01-20T10:00:00.000Z",
        "pull_time": "2024-01-22T15:30:00.000Z",
        "extra_attrs": {
            "architecture": "amd64",
            "os": "linux"
        },
        "annotations": {},
        "references": None,
        "tags": [
            {
                "id": 1,
                "repository_id": 1,
                "artifact_id": 1,
                "name": "latest",
                "push_time": "2024-01-20T10:00:00.000Z",
                "pull_time": "2024-01-22T15:30:00.000Z",
                "immutable": False,
                "signed": False
            },
            {
                "id": 2,
                "repository_id": 1,
                "artifact_id": 1,
                "name": "v1.0.0",
                "push_time": "2024-01-20T10:00:00.000Z",
                "pull_time": "2024-01-21T08:00:00.000Z",
                "immutable": True,
                "signed": True
            }
        ],
        "scan_overview": {
            "application/vnd.security.vulnerability.report; version=1.1": {
                "report_id": "abc123",
                "scan_status": "Success",
                "severity": "High",
                "duration": 30,
                "summary": {
                    "total": 25,
                    "fixable": 15,
                    "summary": {
                        "Critical": 3,
                        "High": 7,
                        "Medium": 10,
                        "Low": 5,
                        "Unknown": 0
                    }
                },
                "start_time": "2024-01-20T10:05:00.000Z",
                "end_time": "2024-01-20T10:05:30.000Z",
                "scanner": {
                    "name": "Trivy",
                    "vendor": "Aqua Security",
                    "version": "v0.48.0"
                },
                "complete_percent": 100
            }
        }
    }


@pytest.fixture
def sample_vulnerability_data() -> Dict[str, Any]:
    """Sample vulnerability data"""
    return {
        "id": "CVE-2024-12345",
        "package": "openssl",
        "version": "1.1.1",
        "fix_version": "1.1.1w",
        "severity": "High",
        "description": "Critical security vulnerability in OpenSSL",
        "links": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-12345"
        ],
        "preferred_cvss": {
            "score_v3": 7.5,
            "vector_v3": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"
        }
    }


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Sample Harbor user data"""
    return {
        "user_id": 1,
        "username": "testuser",
        "email": "testuser@example.com",
        "realname": "Test User",
        "comment": "Test account",
        "admin_role_in_auth": False,
        "creation_time": "2024-01-01T00:00:00.000Z",
        "update_time": "2024-01-10T00:00:00.000Z"
    }


@pytest.fixture
def sample_webhook_payload() -> Dict[str, Any]:
    """Sample webhook payload"""
    return {
        "type": "PUSH_ARTIFACT",
        "occur_at": 1705838400,
        "operator": "admin",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abcdef123456",
                    "tag": "v1.0.1",
                    "resource_url": "harbor.test.com/test-project/test-repo:v1.0.1"
                }
            ],
            "repository": {
                "date_created": 1704067200,
                "name": "test-repo",
                "namespace": "test-project",
                "repo_full_name": "test-project/test-repo",
                "repo_type": "public"
            }
        }
    }


@pytest.fixture
def mock_port_client() -> AsyncMock:
    """Mock Port client"""
    client = AsyncMock()
    client.upsert_entity = AsyncMock()
    client.delete_entity = AsyncMock()
    client.search_entities = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_ocean_context() -> Generator[MagicMock, None, None]:
    """Mock Ocean context for testing"""
    with patch('port_ocean.context.ocean.ocean') as mock:
        mock.integration_config = {
            "harbor_url": "https://harbor.example.com",
            "username": "admin",
            "password": "password",
            "verify_ssl": True
        }
        mock.config = MagicMock()
        mock.config.integration = MagicMock()
        mock.config.integration.identifier = "harbor-test"
        mock.port_client = AsyncMock()
        yield mock


@pytest.fixture
def mock_integration_runtime() -> Generator[MagicMock, None, None]:
    """Mock integration runtime context"""
    with patch("port_ocean.context.ocean.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "harbor_url": "https://harbor.test.com",
            "username": "admin",
            "password": "password",
            "verify_ssl": True
        }
        mock_ocean.port_client = MagicMock()
        yield mock_ocean


@pytest.fixture
def mock_logger() -> Generator[MagicMock, None, None]:
    """Mock logger"""
    with patch("loguru.logger") as mock:
        yield mock


@pytest.fixture(autouse=True)
def cleanup() -> Generator[None, None, None]:
    """Cleanup after each test"""
    yield


def pytest_configure(config: Any) -> None:
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "webhook: marks tests related to webhook handling"
    )
    config.addinivalue_line(
        "markers", "client: marks tests related to Harbor client"
    )