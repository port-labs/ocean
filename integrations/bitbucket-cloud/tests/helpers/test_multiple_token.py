import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict
from bitbucket_cloud.helpers.multiple_token import BitbucketClientManager
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter


@pytest.fixture
def mock_ocean() -> MagicMock:
    """Create a mock ocean context."""
    mock = MagicMock()
    mock.integration_config = MagicMock()
    mock.integration_config.get.return_value = None
    return mock


@pytest.fixture
def mock_bitbucket_client() -> BitbucketClient:
    """Create a mock BitbucketClient."""
    client = MagicMock(spec=BitbucketClient)
    client.set_base_client = MagicMock()
    client.base_client_priority_queue = AsyncMock(spec=asyncio.PriorityQueue)
    return client


@pytest.fixture
def mock_base_client() -> BitbucketBaseClient:
    """Create a mock BitbucketBaseClient."""
    client = MagicMock(spec=BitbucketBaseClient)
    client.base_url = "https://api.bitbucket.org/2.0"
    client.workspace = "test-workspace"
    return client


@pytest.fixture
def mock_limiter() -> RollingWindowLimiter:
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RollingWindowLimiter)
    limiter.has_capacity.return_value = True
    limiter.next_available_time.return_value = 0.0
    return limiter


@pytest.fixture
def client_manager(mock_ocean: MagicMock) -> BitbucketClientManager:
    """Create a BitbucketClientManager instance with mocked dependencies."""
    with patch("bitbucket_cloud.helpers.multiple_token.ocean", mock_ocean):
        return BitbucketClientManager(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            limit_per_client=100,
            window=60.0,
        )


def test_init(client_manager: BitbucketClientManager) -> None:
    """Test initialization of BitbucketClientManager."""
    assert client_manager.workspace == "test-workspace"
    assert client_manager.host == "https://api.bitbucket.org/2.0"
    assert client_manager.limit_per_client == 100
    assert client_manager.window == 60.0
    assert isinstance(client_manager.client_queue, asyncio.PriorityQueue)


def test_parse_credentials_empty(client_manager: BitbucketClientManager) -> None:
    """Test parsing credentials when no credentials are provided."""
    credentials = client_manager._parse_credentials()
    assert credentials == {}


def test_parse_credentials_with_workspace_token(
    client_manager: BitbucketClientManager, mock_ocean: MagicMock
) -> None:
    """Test parsing credentials with workspace token."""
    # Mock the ocean's get method to return the correct values
    mock_ocean.integration_config.get.side_effect = lambda key, default=None: {
        "bitbucket_workspace_token": "token1,token2",
        "bitbucket_username": "",
        "bitbucket_app_password": "",
    }.get(key, default)

    # Mock the ocean module
    with patch("bitbucket_cloud.helpers.multiple_token.ocean", mock_ocean):
        credentials = client_manager._parse_credentials()
        assert len(credentials) == 2
        assert "client_0" in credentials
        assert "client_1" in credentials
        assert credentials["client_0"]["workspace_token"] == "token1"
        assert credentials["client_1"]["workspace_token"] == "token2"


def test_parse_credentials_with_username_password(
    client_manager: BitbucketClientManager, mock_ocean: MagicMock
) -> None:
    """Test parsing credentials with username and app password."""
    # Mock the ocean's get method to return the correct values
    mock_ocean.integration_config.get.side_effect = lambda key, default=None: {
        "bitbucket_workspace_token": "",
        "bitbucket_username": "user1,user2",
        "bitbucket_app_password": "pass1,pass2",
    }.get(key, default)

    # Mock the ocean module
    with patch("bitbucket_cloud.helpers.multiple_token.ocean", mock_ocean):
        credentials = client_manager._parse_credentials()
        assert len(credentials) == 2
        assert "client_0" in credentials
        assert "client_1" in credentials
        assert credentials["client_0"]["username"] == "user1"
        assert credentials["client_0"]["app_password"] == "pass1"
        assert credentials["client_1"]["username"] == "user2"
        assert credentials["client_1"]["app_password"] == "pass2"


def test_add_base_client(
    client_manager: BitbucketClientManager,
    mock_base_client: BitbucketBaseClient,
    mock_limiter: RollingWindowLimiter,
) -> None:
    """Test adding a base client."""
    # Mock the BitbucketBaseClient constructor
    with patch(
        "bitbucket_cloud.helpers.multiple_token.BitbucketBaseClient",
        return_value=mock_base_client,
    ):
        # Mock the RollingWindowLimiter constructor
        with patch(
            "bitbucket_cloud.helpers.multiple_token.RollingWindowLimiter",
            return_value=mock_limiter,
        ):
            # Mock the client_queue
            client_manager.client_queue = MagicMock()
            client_manager.client_queue.put_nowait = MagicMock()

            client_id = "test-client"
            cred = {
                "username": "test-user",
                "app_password": "test-password",
                "workspace_token": None,
            }

            client_manager.add_base_client(client_id, cred)

            assert client_id in client_manager.base_clients
            assert client_id in client_manager.limiters
            client_manager.client_queue.put_nowait.assert_called_once()


def test_initialize_clients_empty(client_manager: BitbucketClientManager) -> None:
    """Test initializing clients when no credentials are provided."""
    # Mock the _parse_credentials method to return empty credentials
    with patch.object(client_manager, "_parse_credentials", return_value={}):
        client_manager._initialize_clients()
        assert len(client_manager.base_clients) == 0
        assert client_manager.client is None


def test_initialize_clients_with_credentials(
    client_manager: BitbucketClientManager,
    mock_bitbucket_client: BitbucketClient,
    mock_base_client: BitbucketBaseClient,
    mock_limiter: RollingWindowLimiter,
) -> None:
    """Test initializing clients with credentials."""
    # Mock the _parse_credentials method to return credentials
    with patch.object(
        client_manager,
        "_parse_credentials",
        return_value={
            "client_0": {
                "username": "test-user",
                "app_password": "test-password",
                "workspace_token": None,
            }
        },
    ):
        # Mock the BitbucketClient constructor
        with patch(
            "bitbucket_cloud.helpers.multiple_token.BitbucketClient",
            return_value=mock_bitbucket_client,
        ):
            # Mock the BitbucketBaseClient constructor
            with patch(
                "bitbucket_cloud.helpers.multiple_token.BitbucketBaseClient",
                return_value=mock_base_client,
            ):
                # Mock the RollingWindowLimiter constructor
                with patch(
                    "bitbucket_cloud.helpers.multiple_token.RollingWindowLimiter",
                    return_value=mock_limiter,
                ):
                    # Mock the client_queue
                    client_manager.client_queue = AsyncMock(spec=asyncio.PriorityQueue)

                    client_manager._initialize_clients()

                    assert len(client_manager.base_clients) == 1
                    assert client_manager.client == mock_bitbucket_client
                    assert mock_bitbucket_client.current_limiter == mock_limiter
                    assert mock_bitbucket_client.client_id == "client_0"
                    assert (
                        mock_bitbucket_client.base_client_priority_queue
                        == client_manager.client_queue
                    )


@pytest.mark.asyncio
async def test_execute_request(
    client_manager: BitbucketClientManager, mock_bitbucket_client: MagicMock
) -> None:
    """Test executing a request."""

    # Create a proper async generator class that yields a single result
    class SuccessGenerator:
        def __init__(self) -> None:
            self._yielded = False

        def __aiter__(self) -> "SuccessGenerator":
            return self

        async def __anext__(self) -> Dict[str, str]:
            if not self._yielded:
                self._yielded = True
                return {"status": "success"}
            raise StopAsyncIteration

    # Set up the mock_bitbucket_client with the GET method that returns an async generator
    mock_bitbucket_client.GET = MagicMock(return_value=SuccessGenerator())

    # Set the client on the manager
    client_manager.client = mock_bitbucket_client

    result = None
    async for item in client_manager.execute_request("GET", "/test"):
        result = item

    assert result == {"status": "success"}
    mock_bitbucket_client.GET.assert_called_once_with("/test")


@pytest.mark.asyncio
async def test_execute_request_with_error(
    client_manager: BitbucketClientManager, mock_bitbucket_client: MagicMock
) -> None:
    """Test executing a request with an error."""

    # Create a proper async generator class that raises an exception
    class ErrorGenerator:
        def __aiter__(self) -> "ErrorGenerator":
            return self

        async def __anext__(self) -> None:
            raise Exception("Test error")

    # Set up the mock_bitbucket_client with the GET method that returns an async generator
    mock_bitbucket_client.GET = MagicMock(return_value=ErrorGenerator())

    # Set the client on the manager
    client_manager.client = mock_bitbucket_client

    with pytest.raises(Exception) as excinfo:
        async for _ in client_manager.execute_request("GET", "/test"):
            pass

    assert "Test error" in str(excinfo.value)
    mock_bitbucket_client.GET.assert_called_once_with("/test")
