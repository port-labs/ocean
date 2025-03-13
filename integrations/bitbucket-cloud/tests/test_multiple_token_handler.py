import pytest
import time
from collections import deque
from unittest.mock import patch, AsyncMock, MagicMock
from helpers.multiple_token_handler import (
    TokenClient,
    MultiTokenBitbucketClient,
)
from httpx import Response, HTTPStatusError, Request
from port_ocean.utils import http_async_client
import base64
from typing import Generator, Tuple, AsyncGenerator


@pytest.fixture
def token_str() -> str:
    return "test_token"


@pytest.fixture
def token_tuple() -> Tuple[str, str]:
    return ("username", "password")


@pytest.fixture
def base_url() -> str:
    return "https://api.test.com"


@pytest.fixture
def mock_response() -> MagicMock:
    mock = MagicMock(spec=Response)
    mock.status_code = 200
    mock.json.return_value = {"data": "test"}
    return mock


@pytest.fixture
def mock_rate_limited_response() -> MagicMock:
    mock = MagicMock(spec=Response)
    mock.status_code = 429
    mock.json.return_value = {"message": "Rate limited"}
    mock.raise_for_status.side_effect = HTTPStatusError(
        "Rate limited", request=Request("GET", "https://api.test.com"), response=mock
    )
    return mock


# Save original headers and auth to restore after tests
@pytest.fixture(autouse=True)
def clean_http_client() -> Generator[None, None, None]:
    # Save original headers
    original_headers = http_async_client.headers.copy()

    # Run the test
    yield

    # Restore original headers
    for key in list(http_async_client.headers.keys()):
        if key not in original_headers:
            del http_async_client.headers[key]
        else:
            http_async_client.headers[key] = original_headers[key]


@pytest.fixture
async def token_client(
    token_str: str, base_url: str
) -> AsyncGenerator[TokenClient, None]:
    client = TokenClient(
        token=token_str,
        base_url=base_url,
        requests_per_hour=10,
        window=0.5,  # Use shorter window for faster tests
    )
    yield client
    # Don't call close since the client is shared


@pytest.fixture
async def multi_token_client() -> AsyncGenerator[MultiTokenBitbucketClient, None]:
    """Create multi token client with controlled parameters for testing."""
    client = MultiTokenBitbucketClient(
        credentials=["token1", "token2"],
        requests_per_hour=5,
        window=3600,  # Use int as required by type annotation
    )
    yield client
    # Don't close the shared http client


@pytest.mark.asyncio
async def test_token_client_str_token_setup(
    token_str: str, base_url: str, clean_http_client: None
) -> None:
    """Test TokenClient initialization with string token."""
    client = TokenClient(
        token=token_str, base_url=base_url, requests_per_hour=1000, window=3600
    )

    assert client.token == token_str
    assert "Bearer" in http_async_client.headers["Authorization"]
    assert http_async_client.headers["Authorization"] == f"Bearer {token_str}"
    assert client.base_url == base_url
    assert client.rate_limiter.limit == 1000
    assert client.rate_limiter.window == 3600


@pytest.mark.asyncio
async def test_token_client_tuple_token_setup(
    token_tuple: Tuple[str, str], base_url: str, clean_http_client: None
) -> None:
    """Test TokenClient initialization with username/password tuple."""
    client = TokenClient(
        token=token_tuple, base_url=base_url, requests_per_hour=1000, window=3600
    )

    assert client.token == token_tuple
    assert "Basic" in http_async_client.headers["Authorization"]
    auth = base64.b64encode(f"{token_tuple[0]}:{token_tuple[1]}".encode()).decode()
    assert http_async_client.headers["Authorization"] == f"Basic {auth}"
    assert client.base_url == base_url


@pytest.mark.asyncio
async def test_multi_token_client_initialization(
    token_str: str, token_tuple: Tuple[str, str], clean_http_client: None
) -> None:
    """Test MultiTokenBitbucketClient initialization."""
    client = MultiTokenBitbucketClient(
        credentials=[token_str, token_tuple], requests_per_hour=1000, window=3600
    )

    assert len(client.token_clients) == 2
    assert isinstance(client.token_clients[0], TokenClient)
    assert isinstance(client.token_clients[1], TokenClient)
    assert client.current_client_index == 0
    assert client.base_url == "https://api.bitbucket.org/2.0"

    # We can't test headers directly since they're all on the same client


@pytest.mark.asyncio
async def test_multi_token_client_rotation(
    multi_token_client: MultiTokenBitbucketClient,
) -> None:
    """Test client rotation functionality."""
    assert len(multi_token_client.token_clients) == 2
    initial_index = multi_token_client.current_client_index
    assert initial_index == 0

    # Store reference to first client
    initial_client = multi_token_client.get_current_client()

    # Rotate
    multi_token_client._rotate_client()

    # Verify rotation occurred
    assert multi_token_client.current_client_index == 1
    assert multi_token_client.get_current_client() is not initial_client


@pytest.mark.asyncio
async def test_find_available_client() -> None:
    """Test finding available client with controlled mocking."""
    # Create a client with shorter window
    client = MultiTokenBitbucketClient(
        credentials=["token1", "token2"],
        requests_per_hour=5,
        window=3600,  # Use int as required by type annotation
    )

    try:
        # First client should be available initially
        available = await client._find_available_client()
        assert available is not None
        assert available == client.get_current_client()

        # Test with the first client at capacity
        # Use deque instead of list for timestamps
        with patch.object(
            client.token_clients[0].rate_limiter,
            "_timestamps",
            deque([time.monotonic() for _ in range(5)]),
        ):

            # Second client should be available
            available = await client._find_available_client()
            assert available is not None
            assert available == client.token_clients[1]

            # Test with both clients at capacity
            with patch.object(
                client.token_clients[1].rate_limiter,
                "_timestamps",
                deque([time.monotonic() for _ in range(5)]),
            ):

                # No client should be available
                available = await client._find_available_client()
                assert available is None

                # After waiting, the first client should become available
                # Use a patch for purge instead of calling it directly
                future_time = time.monotonic() + 1.0  # Well past window expiry
                with patch("time.monotonic", return_value=future_time):
                    # Set timestamps to empty list to simulate purged timestamps
                    client.token_clients[0].rate_limiter._timestamps = deque()

                    # Now try to find available client
                    available = await client._find_available_client()
                    assert available is not None
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.mark.asyncio
async def test_rate_limit_context_non_repo_endpoint(
    multi_token_client: MultiTokenBitbucketClient,
) -> None:
    """Test rate limit context manager with non-repository endpoint."""
    # Non-repo endpoints should bypass rate limiting
    async with multi_token_client.rate_limit("users/test") as should_rotate:
        assert should_rotate is False


@pytest.mark.asyncio
async def test_rate_limit_context_repo_endpoint() -> None:
    """Test rate limit context manager with repository endpoint using controlled mocking."""
    # Create a fresh client for this test
    client = MultiTokenBitbucketClient(
        credentials=["token1", "token2"],
        requests_per_hour=5,
        window=3600,  # Use int as required by type annotation
    )

    try:
        # First request shouldn't need rotation
        async with client.rate_limit("repositories/test") as should_rotate:
            # The context now always returns False since rotation is handled internally
            assert should_rotate is False

        # Mock the first client at capacity
        with patch.object(
            client.token_clients[0].rate_limiter,
            "_timestamps",
            deque([time.monotonic() for _ in range(5)]),
        ):

            # Patching find_available_client to simulate switching to second client
            with patch.object(
                client, "_find_available_client", new_callable=AsyncMock
            ) as mock_find:
                mock_find.return_value = client.token_clients[1]

                # Get initial client index
                initial_index = client.current_client_index

                # Next request should internally switch to second client
                async with client.rate_limit("repositories/test") as should_rotate:
                    # The should_rotate value doesn't actually indicate rotation anymore
                    # since rotation happens internally
                    pass

                # Verify that find_available_client was called
                assert mock_find.called

                # Check if rotation happened as expected
                assert client.current_client_index != initial_index
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.mark.asyncio
async def test_multi_token_client_error_handling() -> None:
    """Test error handling in rate limit context."""
    # Create a fresh client for this test
    client = MultiTokenBitbucketClient(
        credentials=["token1", "token2"],
        requests_per_hour=5,
        window=3600,  # Use int as required by type annotation
    )

    try:
        initial_client_index = client.current_client_index

        # Test exception propagation
        with pytest.raises(Exception) as excinfo:
            async with client.rate_limit("repositories/test"):
                raise Exception("Test error")

        assert "Test error" in str(excinfo.value)

        # Client index should remain the same even after exception
        assert client.current_client_index == initial_client_index
    except Exception as e:
        pytest.fail(f"Test failed with unexpected exception: {e}")


@pytest.mark.asyncio
async def test_client_close() -> None:
    """Test proper cleanup of clients."""
    # Create temp client with patched close method to verify it's called
    with patch.object(
        http_async_client, "aclose", new_callable=AsyncMock
    ) as mock_close:
        client = MultiTokenBitbucketClient(
            credentials=["token1", "token2"],
            requests_per_hour=5,
            window=3600,  # Use int as required by type annotation
        )

        await client.close()

        # Verify close was called
        assert mock_close.called


@pytest.mark.asyncio
async def test_empty_credentials() -> None:
    """Test initialization with empty credentials list."""
    with pytest.raises(ValueError) as excinfo:
        MultiTokenBitbucketClient(credentials=[], requests_per_hour=1000, window=3600)

    assert "At least one credential is required" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_current_client(
    multi_token_client: MultiTokenBitbucketClient,
) -> None:
    """Test get_current_client returns the correct client."""
    client = multi_token_client.get_current_client()
    assert (
        client
        is multi_token_client.token_clients[multi_token_client.current_client_index]
    )

    # After rotation, should return the new current client
    multi_token_client._rotate_client()
    new_client = multi_token_client.get_current_client()
    assert (
        new_client
        is multi_token_client.token_clients[multi_token_client.current_client_index]
    )
    assert new_client is not client


@pytest.mark.asyncio
async def test_rate_limit_with_client_exhaustion() -> None:
    """Test behavior when all clients are exhausted, with controlled time mocking."""
    # Create a client specifically for this test with shorter window
    client = MultiTokenBitbucketClient(
        credentials=["token1", "token2"],
        requests_per_hour=5,
        window=3600,  # Use int as required by type annotation
    )

    try:
        # Mock time to control the test
        mock_time = 1000.0  # Arbitrary start time

        with patch("time.monotonic", return_value=mock_time):
            # Set both clients to be at capacity with deques instead of lists
            client.token_clients[0].rate_limiter._timestamps = deque(
                [mock_time - 0.4 for _ in range(5)]
            )
            client.token_clients[1].rate_limiter._timestamps = deque(
                [mock_time - 0.1 for _ in range(5)]
            )

            # Both clients are at capacity, no client should be immediately available
            available = await client._find_available_client()
            assert available is None

            # Now advance time to expire first client's timestamps
            future_time = mock_time + 0.5  # Past window expiry

            with patch("time.monotonic", return_value=future_time):
                # Set timestamps to empty deque to simulate cleared timestamps
                client.token_clients[0].rate_limiter._timestamps = deque()

                # This should now find the first client available
                available = await client._find_available_client()
                assert available is not None
                assert available == client.token_clients[0]
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.mark.asyncio
async def test_wait_for_soonest_available_client() -> None:
    """Test that we switch to the client that will be available soonest."""
    # Create a client specifically for this test
    client = MultiTokenBitbucketClient(
        credentials=["token1", "token2"],
        requests_per_hour=5,
        window=3600,  # Use int as required by type annotation
    )

    try:
        # Control the current time
        current_time = 1000.0

        with patch("time.monotonic", return_value=current_time):
            # Set up first client with newer timestamps (will expire later)
            client.token_clients[0].rate_limiter._timestamps = deque(
                [current_time - 0.1 for _ in range(5)]
            )

            # Set up second client with older timestamp (will expire sooner)
            client.token_clients[1].rate_limiter._timestamps = deque(
                [current_time - 0.4]
            )  # Just one timestamp

            # Override find_available_client to make sure the test uses the right client
            with patch.object(
                client, "_find_available_client", new_callable=AsyncMock
            ) as mock_find:
                # First call returns None (no immediate client)
                # Second call finds client[1] (for switching to soonest)
                mock_find.side_effect = [None, client.token_clients[1]]

                # Store original index
                initial_index = client.current_client_index

                # Should switch to second client
                async with client.rate_limit("repositories/test"):
                    # The context doesn't return True/False for rotation anymore
                    pass

                # Verify that we've checked for available clients
                assert mock_find.call_count > 0

                # Verify that we switched to the second client
                assert client.current_client_index != initial_index
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")
