import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, List, Tuple
from bitbucket_cloud.base_rotating_client import BaseRotatingClient
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter


@pytest.fixture
def mock_base_client() -> BitbucketBaseClient:
    """Create a mock base client."""
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
def rotating_client() -> BaseRotatingClient:
    """Create a BaseRotatingClient instance."""
    return BaseRotatingClient()


@pytest.fixture
def mock_priority_queue() -> MagicMock:
    """Create a mock priority queue."""
    queue = MagicMock(
        spec=asyncio.PriorityQueue[
            Tuple[float, str, BitbucketBaseClient, RollingWindowLimiter]
        ]
    )
    queue.get = AsyncMock()
    queue.put_nowait = MagicMock()
    return queue


def test_init(rotating_client: BaseRotatingClient) -> None:
    """Test initialization of BaseRotatingClient."""
    assert rotating_client.base_client is None
    assert rotating_client.current_limiter is None
    assert rotating_client.client_id is None
    assert rotating_client.base_client_priority_queue is None
    assert rotating_client.base_url is None
    assert rotating_client.workspace is None


def test_set_base_client(
    rotating_client: BaseRotatingClient, mock_base_client: BitbucketBaseClient
) -> None:
    """Test setting the base client."""
    rotating_client.set_base_client(mock_base_client)
    assert rotating_client.base_client == mock_base_client
    assert rotating_client.base_url == mock_base_client.base_url
    assert rotating_client.workspace == mock_base_client.workspace


def test_update_client_state(
    rotating_client: BaseRotatingClient,
    mock_base_client: BitbucketBaseClient,
    mock_limiter: RollingWindowLimiter,
) -> None:
    """Test updating client state."""
    client_id = "test-client"
    rotating_client._update_client_state(client_id, mock_base_client, mock_limiter)
    assert rotating_client.base_client == mock_base_client
    assert rotating_client.current_limiter == mock_limiter
    assert rotating_client.client_id == client_id


def test_put_clients_back_in_queue(
    rotating_client: BaseRotatingClient, mock_priority_queue: MagicMock
) -> None:
    """Test putting clients back in the queue."""
    rotating_client.base_client_priority_queue = mock_priority_queue
    all_clients: List[Tuple[Any, ...]] = [
        (0.0, "client1", MagicMock(), MagicMock()),
        (0.0, "client2", MagicMock(), MagicMock()),
    ]
    rotating_client._put_clients_back_in_queue(all_clients)
    assert mock_priority_queue.put_nowait.call_count == 2


def test_put_clients_back_in_queue_none_queue(
    rotating_client: BaseRotatingClient,
) -> None:
    """Test putting clients back in the queue when queue is None."""
    rotating_client.base_client_priority_queue = None
    all_clients: List[Tuple[Any, ...]] = [
        (0.0, "client1", MagicMock(), MagicMock()),
        (0.0, "client2", MagicMock(), MagicMock()),
    ]
    # Should not raise an exception
    rotating_client._put_clients_back_in_queue(all_clients)


@pytest.mark.asyncio
async def test_handle_client_with_capacity(
    rotating_client: BaseRotatingClient,
    mock_base_client: BitbucketBaseClient,
    mock_limiter: RollingWindowLimiter,
    mock_priority_queue: MagicMock,
) -> None:
    """Test handling a client with capacity."""
    rotating_client.base_client_priority_queue = mock_priority_queue
    client_id = "test-client"
    all_clients: List[Tuple[Any, ...]] = [
        (0.0, "client1", MagicMock(), MagicMock()),
        (0.0, "client2", MagicMock(), MagicMock()),
    ]
    result = rotating_client._handle_client_with_capacity(
        client_id, mock_base_client, mock_limiter, all_clients
    )
    assert result == (client_id, mock_base_client, mock_limiter)
    assert mock_priority_queue.put_nowait.call_count == 2


@pytest.mark.asyncio
async def test_handle_client_without_capacity(
    rotating_client: BaseRotatingClient,
    mock_base_client: BitbucketBaseClient,
    mock_limiter: RollingWindowLimiter,
    mock_priority_queue: MagicMock,
) -> None:
    """Test handling a client without capacity."""
    rotating_client.base_client_priority_queue = mock_priority_queue
    client_id = "test-client"
    tried_clients: set[str] = set()
    all_clients: List[Tuple[Any, ...]] = [
        (0.0, "client1", MagicMock(), MagicMock()),
        (0.0, "client2", MagicMock(), MagicMock()),
    ]
    current_time = 0.0

    # Mock the _find_earliest_available_client method
    with patch.object(
        rotating_client, "_find_earliest_available_client", new_callable=AsyncMock
    ) as mock_find_earliest:
        mock_find_earliest.return_value = (None, None, None)
        result = await rotating_client._handle_client_without_capacity(
            client_id,
            mock_base_client,
            mock_limiter,
            tried_clients,
            all_clients,
            current_time,
        )
        assert result is None
        assert client_id in tried_clients
        mock_priority_queue.put_nowait.assert_called_once()


@pytest.mark.asyncio
async def test_get_next_client_from_queue(
    rotating_client: BaseRotatingClient, mock_priority_queue: MagicMock
) -> None:
    """Test getting the next client from the queue."""
    rotating_client.base_client_priority_queue = mock_priority_queue
    mock_base_client = MagicMock()
    mock_limiter = MagicMock()
    mock_limiter.has_capacity.return_value = True

    # Mock the queue.get method to return a client
    mock_priority_queue.get.return_value = (
        0.0,
        "test-client",
        mock_base_client,
        mock_limiter,
    )

    result = await rotating_client._get_next_client_from_queue()
    assert result == ("test-client", mock_base_client, mock_limiter)


@pytest.mark.asyncio
async def test_get_next_client_from_queue_empty(
    rotating_client: BaseRotatingClient, mock_priority_queue: MagicMock
) -> None:
    """Test getting the next client from an empty queue."""
    rotating_client.base_client_priority_queue = mock_priority_queue

    # Mock the queue.get method to raise QueueEmpty
    mock_priority_queue.get.side_effect = asyncio.QueueEmpty()

    result = await rotating_client._get_next_client_from_queue()
    assert result == (None, None, None)


@pytest.mark.asyncio
async def test_find_earliest_available_client(
    rotating_client: BaseRotatingClient,
) -> None:
    """Test finding the earliest available client."""
    mock_base_client1 = MagicMock()
    mock_limiter1 = MagicMock()
    mock_limiter1.has_capacity.return_value = False
    mock_limiter1.next_available_time.return_value = 10.0

    mock_base_client2 = MagicMock()
    mock_limiter2 = MagicMock()
    mock_limiter2.has_capacity.return_value = False
    mock_limiter2.next_available_time.return_value = 5.0

    all_clients: List[Tuple[float, str, Any, Any]] = [
        (0.0, "client1", mock_base_client1, mock_limiter1),
        (0.0, "client2", mock_base_client2, mock_limiter2),
    ]
    current_time = 0.0

    # Mock the _put_clients_back_in_queue method
    with patch.object(rotating_client, "_put_clients_back_in_queue") as mock_put_back:
        result = await rotating_client._find_earliest_available_client(
            all_clients, current_time
        )
        assert result == ("client2", mock_base_client2, mock_limiter2)
        mock_put_back.assert_called_once_with(all_clients)


@pytest.mark.asyncio
async def test_ensure_client_available(
    rotating_client: BaseRotatingClient,
) -> None:
    """Test ensuring a client is available."""
    # Mock the _get_next_client_from_queue method
    with patch.object(
        rotating_client, "_get_next_client_from_queue", new_callable=AsyncMock
    ) as mock_get_next:
        mock_base_client = MagicMock()
        mock_limiter = MagicMock()
        mock_limiter.has_capacity.return_value = True
        mock_get_next.return_value = ("test-client", mock_base_client, mock_limiter)

        # Mock the _update_client_state method
        with patch.object(rotating_client, "_update_client_state") as mock_update:
            # Mock the _rotate_base_client method to avoid the second call
            with patch.object(
                rotating_client, "_rotate_base_client", new_callable=AsyncMock
            ) as mock_rotate:
                # Set the current limiter to None to trigger rotation
                rotating_client.current_limiter = None
                await rotating_client._ensure_client_available()

                # Verify _update_client_state was called once
                mock_update.assert_called_once_with(
                    "test-client", mock_base_client, mock_limiter
                )

                # Verify _rotate_base_client was called
                mock_rotate.assert_called_once()


@pytest.mark.asyncio
async def test_rotate_base_client(
    rotating_client: BaseRotatingClient,
) -> None:
    """Test rotating to the next base client."""
    # Mock the _get_next_client_from_queue method
    with patch.object(
        rotating_client, "_get_next_client_from_queue", new_callable=AsyncMock
    ) as mock_get_next:
        mock_base_client = MagicMock()
        mock_limiter = MagicMock()
        mock_get_next.return_value = ("test-client", mock_base_client, mock_limiter)

        # Mock the _update_client_state method
        with patch.object(rotating_client, "_update_client_state") as mock_update:
            await rotating_client._rotate_base_client()
            mock_update.assert_called_once_with(
                "test-client", mock_base_client, mock_limiter
            )
