import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Generator

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

MOCK_ORG_URL: str = "https://mock-organization-url.com"
MOCK_PERSONAL_ACCESS_TOKEN: str = "mock-personal_access_token"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""
    try:
        mock_ocean_app: MagicMock = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Mock the event context."""
    mock_event: MagicMock = MagicMock(spec=EventContext)

    with patch("port_ocean.context.event.event_context", mock_event):
        yield mock_event


@pytest.fixture
def mock_aiosession() -> AsyncMock:
    """Creates a mocked AioSession with client factory and credentials."""
    mock_session: AsyncMock = AsyncMock()
    mock_session.region_name = "us-west-2"

    @asynccontextmanager
    async def mock_client(
        service_name: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        if service_name == "sts":
            mock_sts_client: AsyncMock = AsyncMock()
            mock_sts_client.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "mock_access_key",
                    "SecretAccessKey": "mock_secret_key",
                    "SessionToken": "mock_session_token",
                    "Expiration": "2024-12-31T23:59:59Z",
                }
            }
            mock_sts_client.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:sts::123456789012:assumed-role/test-role/test-session",
                "UserId": "AIDACKCEVSQ6C2EXAMPLE",
            }
            yield mock_sts_client
        elif service_name == "account":
            mock_account_client: AsyncMock = AsyncMock()
            mock_account_client.list_regions.return_value = {
                "Regions": [
                    {"RegionName": "us-east-1", "RegionOptStatus": "ENABLED"},
                    {"RegionName": "us-west-2", "RegionOptStatus": "ENABLED"},
                    {"RegionName": "eu-west-1", "RegionOptStatus": "ENABLED"},
                ]
            }
            yield mock_account_client
        else:
            raise NotImplementedError(f"Client for service '{service_name}' not mocked")

    # Provide a mock for get_credentials
    class MockFrozenCredentials:
        access_key: str = "mock_access_key"
        secret_key: str = "mock_secret_key"
        token: str = "mock_session_token"

    class MockCredentials:
        async def get_frozen_credentials(self) -> MockFrozenCredentials:
            return MockFrozenCredentials()

    mock_session.get_credentials.return_value = MockCredentials()
    mock_session.create_client = mock_client
    return mock_session


@pytest.fixture
def mock_account_id() -> str:
    """Mocks the account ID."""
    return "123456789012"


@pytest.fixture
def mock_role_arn() -> str:
    """Mocks a role ARN."""
    return "arn:aws:iam::123456789012:role/test-role"


@pytest.fixture
def mock_external_id() -> str:
    """Mocks an external ID."""
    return "test-external-id"


@pytest.fixture
def mock_aws_config() -> Dict[str, Any]:
    """Mocks AWS configuration."""
    return {
        "aws_access_key_id": "test_access_key",
        "aws_secret_access_key": "test_secret_key",
        "aws_session_token": "test_session_token",
        "region": "us-west-2",
        "external_id": "test-external-id",
    }


@pytest.fixture
def mock_multi_account_config() -> Dict[str, Any]:
    """Mocks multi-account AWS configuration."""
    return {
        "account_role_arns": [
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        ],
        "region": "us-west-2",
        "external_id": "test-external-id",
    }


@pytest.fixture
def mock_single_account_config() -> Dict[str, Any]:
    """Mocks single account AWS configuration."""
    return {
        "aws_access_key_id": "test_access_key",
        "aws_secret_access_key": "test_secret_key",
        "aws_session_token": "test_session_token",
        "region": "us-west-2",
    }


@pytest.fixture
def mock_aiocredentials() -> MagicMock:
    """Mocks AioCredentials."""
    mock_creds = MagicMock()
    mock_creds.access_key = "test_access_key"
    mock_creds.secret_key = "test_secret_key"
    mock_creds.token = "test_session_token"
    return mock_creds


@pytest.fixture
def mock_aiorefreshable_credentials() -> MagicMock:
    """Mocks AioRefreshableCredentials."""
    mock_creds = MagicMock()
    mock_creds.access_key = "test_access_key"
    mock_creds.secret_key = "test_secret_key"
    mock_creds.token = "test_session_token"
    mock_creds.refresh_needed.return_value = False
    return mock_creds


@pytest.fixture
def mock_arn_parser() -> MagicMock:
    """Mocks ArnParser."""
    mock_parser = MagicMock()
    mock_parser.parse_arn.return_value = {
        "partition": "aws",
        "service": "iam",
        "region": "",
        "account": "123456789012",
        "resource": "role/test-role",
    }
    return mock_parser


@pytest.fixture
def mock_selector() -> MagicMock:
    """Mocks AWSDescribeResourcesSelector."""
    mock_selector = MagicMock()
    mock_selector.is_region_allowed.return_value = True
    return mock_selector


@pytest.fixture(autouse=True)
def mock_logger() -> Generator[None, None, None]:
    """Mock logger to prevent actual logging during tests."""
    with patch("loguru.logger"):
        yield


@pytest.fixture
def mock_assume_role_refresher() -> MagicMock:
    """Mocks the assume role refresher function."""

    def _refresher_factory(*args: Any, **kwargs: Any) -> Any:
        async def refresher() -> dict[str, str]:
            return {
                "access_key": "test_access_key",
                "secret_key": "test_secret_key",
                "token": "test_session_token",
                "expiry_time": "2024-12-31T23:59:59Z",
            }

        return refresher

    mock = MagicMock(side_effect=_refresher_factory)
    return mock
