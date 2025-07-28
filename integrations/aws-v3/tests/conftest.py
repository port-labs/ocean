import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Generator
from datetime import datetime, timedelta

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from aws.auth.session_factory import ResyncStrategyFactory

MOCK_ORG_URL: str = "https://mock-organization-url.com"
MOCK_PERSONAL_ACCESS_TOKEN: str = "mock-personal_access_token"

AWS_TEST_ACCOUNT_ID: str = "123456789012"
AWS_TEST_ACCOUNT_ID_2: str = "987654321098"
AWS_TEST_ACCESS_KEY: str = "test_access_key"
AWS_TEST_SECRET_KEY: str = "test_secret_key"
AWS_TEST_SESSION_TOKEN: str = "test_session_token"
AWS_TEST_REGION: str = "us-west-2"
AWS_TEST_EXTERNAL_ID: str = "test-external-id"
AWS_TEST_ROLE_ARN: str = f"arn:aws:iam::{AWS_TEST_ACCOUNT_ID}:role/test-role"
AWS_TEST_ROLE_ARN_1: str = f"arn:aws:iam::{AWS_TEST_ACCOUNT_ID}:role/test-role-1"
AWS_TEST_ROLE_ARN_2: str = "arn:aws:iam::987654321098:role/test-role-2"
AWS_TEST_USER_ID: str = "AIDACKCEVSQ6C2EXAMPLE"


AWS_TEST_EXPIRATION: str = (datetime.now() + timedelta(hours=1)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

AWS_STS_CREDENTIALS_RESPONSE: Dict[str, Any] = {
    "Credentials": {
        "AccessKeyId": AWS_TEST_ACCESS_KEY,
        "SecretAccessKey": AWS_TEST_SECRET_KEY,
        "SessionToken": AWS_TEST_SESSION_TOKEN,
        "Expiration": AWS_TEST_EXPIRATION,
    }
}

AWS_STS_CALLER_IDENTITY_RESPONSE: Dict[str, Any] = {
    "Account": AWS_TEST_ACCOUNT_ID,
    "Arn": f"arn:aws:sts::{AWS_TEST_ACCOUNT_ID}:assumed-role/test-role/test-session",
    "UserId": AWS_TEST_USER_ID,
}

AWS_ACCOUNT_REGIONS_RESPONSE: Dict[str, Any] = {
    "Regions": [
        {"RegionName": "us-east-1", "RegionOptStatus": "ENABLED"},
        {"RegionName": "us-west-2", "RegionOptStatus": "ENABLED"},
        {"RegionName": "eu-west-1", "RegionOptStatus": "ENABLED"},
    ]
}

AWS_ACCOUNT_INFO_TEMPLATE: Dict[str, str] = {
    "Id": AWS_TEST_ACCOUNT_ID,
    "Name": f"Account {AWS_TEST_ACCOUNT_ID}",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests."""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "aws_access_key_id": AWS_TEST_ACCESS_KEY,
            "aws_secret_access_key": AWS_TEST_SECRET_KEY,
            "aws_session_token": AWS_TEST_SESSION_TOKEN,
            "region": AWS_TEST_REGION,
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Mock the event context."""
    mock_event: MagicMock = MagicMock(spec=EventContext)

    with patch("port_ocean.context.event.event_context", mock_event):
        yield mock_event


@pytest.fixture
def mock_account_id() -> str:
    """Mocks the account ID."""
    return AWS_TEST_ACCOUNT_ID


@pytest.fixture
def mock_role_arn() -> str:
    """Mocks a role ARN."""
    return AWS_TEST_ROLE_ARN


@pytest.fixture
def mock_external_id() -> str:
    """Mocks an external ID."""
    return AWS_TEST_EXTERNAL_ID


@pytest.fixture
def mock_aws_config() -> Dict[str, Any]:
    """Mocks AWS configuration."""
    return {
        "aws_access_key_id": AWS_TEST_ACCESS_KEY,
        "aws_secret_access_key": AWS_TEST_SECRET_KEY,
        "aws_session_token": AWS_TEST_SESSION_TOKEN,
        "region": AWS_TEST_REGION,
        "external_id": AWS_TEST_EXTERNAL_ID,
    }


@pytest.fixture
def mock_multi_account_config() -> Dict[str, Any]:
    """Mocks multi-account AWS configuration."""
    return {
        "account_role_arn": [
            AWS_TEST_ROLE_ARN_1,
            AWS_TEST_ROLE_ARN_2,
        ],
        "region": AWS_TEST_REGION,
        "external_id": AWS_TEST_EXTERNAL_ID,
    }


@pytest.fixture
def mock_single_account_config() -> Dict[str, Any]:
    """Mocks single account AWS configuration."""
    return {
        "aws_access_key_id": AWS_TEST_ACCESS_KEY,
        "aws_secret_access_key": AWS_TEST_SECRET_KEY,
        "aws_session_token": AWS_TEST_SESSION_TOKEN,
        "region": AWS_TEST_REGION,
    }


@pytest.fixture
def mock_selector() -> MagicMock:
    """Mocks AWSDescribeResourcesSelector."""
    mock_selector = MagicMock()
    mock_selector.is_region_allowed.return_value = True
    return mock_selector


@pytest.fixture(scope="function", autouse=True)
def reset_cached_strategy() -> Generator[None, None, None]:
    """Reset the cached strategy before and after each test."""
    original_cache = getattr(ResyncStrategyFactory, "_cached_strategy", None)

    ResyncStrategyFactory._cached_strategy = None

    yield

    ResyncStrategyFactory._cached_strategy = original_cache


@pytest.fixture(autouse=True)
def mock_logger() -> Generator[None, None, None]:
    """Mock logger to prevent actual logging during tests."""
    with patch("loguru.logger"):
        yield


@pytest.fixture
def mock_assume_role_refresher() -> MagicMock:
    """Mocks the assume role refresher function."""

    async def _refresher_factory(*args: Any, **kwargs: Any) -> dict[str, str]:
        return {
            "access_key": AWS_TEST_ACCESS_KEY,
            "secret_key": AWS_TEST_SECRET_KEY,
            "token": AWS_TEST_SESSION_TOKEN,
            "expiry_time": AWS_TEST_EXPIRATION,
        }

    mock = MagicMock(side_effect=_refresher_factory)
    return mock


@pytest.fixture
def aws_credentials() -> Dict[str, str]:
    """Provides AWS credentials for testing."""
    return {
        "aws_access_key_id": AWS_TEST_ACCESS_KEY,
        "aws_secret_access_key": AWS_TEST_SECRET_KEY,
        "aws_session_token": AWS_TEST_SESSION_TOKEN,
    }


@pytest.fixture
def aws_credentials_without_token() -> Dict[str, str]:
    """Provides AWS credentials without session token for testing."""
    return {
        "aws_access_key_id": AWS_TEST_ACCESS_KEY,
        "aws_secret_access_key": AWS_TEST_SECRET_KEY,
    }


@pytest.fixture
def role_arn() -> str:
    """Provides a test role ARN."""
    return AWS_TEST_ROLE_ARN


@pytest.fixture
def multi_account_config(role_arn: str) -> Dict[str, Any]:
    """Provides multi-account configuration."""
    return {
        "account_role_arn": [role_arn],
        "region": AWS_TEST_REGION,
        "external_id": AWS_TEST_EXTERNAL_ID,
    }


@pytest.fixture
def oidc_config(role_arn: str) -> Dict[str, Any]:
    """Provides OIDC configuration."""
    return {
        "oidc_token": "test-oidc-token",
        "account_role_arn": [role_arn],
        "region": AWS_TEST_REGION,
    }


@pytest.fixture
def mock_sts_client() -> AsyncMock:
    """Provides a mock STS client with common responses."""
    mock_client = AsyncMock()
    mock_client.get_caller_identity.return_value = AWS_STS_CALLER_IDENTITY_RESPONSE
    mock_client.assume_role.return_value = AWS_STS_CREDENTIALS_RESPONSE
    return mock_client


@pytest.fixture
def mock_account_client() -> AsyncMock:
    """Provides a mock account client with region responses."""
    mock_client = AsyncMock()
    mock_client.list_regions.return_value = AWS_ACCOUNT_REGIONS_RESPONSE
    return mock_client


@pytest.fixture
def mock_session_with_account_client(mock_account_client: AsyncMock) -> AsyncMock:
    """Provides a mock session that returns the mock account client."""
    session = AsyncMock()

    @asynccontextmanager
    async def mock_create_client(
        service_name: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        if service_name == "account":
            yield mock_account_client
        else:
            other_client = AsyncMock()
            other_client.side_effect = Exception(f"Service {service_name} not mocked")
            yield other_client

    session.create_client = mock_create_client
    return session


@pytest.fixture
def mock_session_with_sts_client(mock_sts_client: AsyncMock) -> AsyncMock:
    """Provides a mock session that returns the mock STS client."""
    session = AsyncMock()

    @asynccontextmanager
    async def mock_create_client(
        service_name: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        if service_name == "sts":
            yield mock_sts_client
        else:
            other_client = AsyncMock()
            other_client.side_effect = Exception(f"Service {service_name} not mocked")
            yield other_client

    session.create_client = mock_create_client
    return session


@pytest.fixture
def mock_aio_session() -> Generator[MagicMock, None, None]:
    """Mock AioSession for provider tests."""
    with patch("aiobotocore.session.AioSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        yield mock_session
