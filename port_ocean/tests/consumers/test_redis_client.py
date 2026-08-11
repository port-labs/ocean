from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from port_ocean.consumers.redis_client import (
    calculate_exponential_backoff_seconds,
    create_redis_client,
    create_redis_client_with_retry,
    is_redis_cluster_enabled,
)


class TestIsRedisClusterEnabled:
    @pytest.mark.asyncio
    async def test_returns_true_when_cluster_enabled(self) -> None:
        redis_client = AsyncMock()
        redis_client.info = AsyncMock(return_value={"cluster_enabled": 1})

        assert await is_redis_cluster_enabled(redis_client) is True
        redis_client.info.assert_awaited_once_with("cluster")

    @pytest.mark.asyncio
    async def test_returns_false_when_cluster_disabled(self) -> None:
        redis_client = AsyncMock()
        redis_client.info = AsyncMock(return_value={"cluster_enabled": 0})

        assert await is_redis_cluster_enabled(redis_client) is False


class TestCreateRedisClient:
    @pytest.mark.asyncio
    async def test_returns_standalone_client_when_cluster_disabled(self) -> None:
        mock_standalone = AsyncMock()
        mock_standalone.info = AsyncMock(return_value={"cluster_enabled": 0})

        with patch(
            "port_ocean.consumers.redis_client.Redis.from_url",
            return_value=mock_standalone,
        ) as mock_from_url:
            client = await create_redis_client(
                "redis://localhost:6379",
                decode_responses=True,
            )

        assert client is mock_standalone
        mock_from_url.assert_called_once_with(
            "redis://localhost:6379",
            decode_responses=True,
        )
        mock_standalone.aclose.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_cluster_client_when_cluster_enabled(self) -> None:
        mock_standalone = AsyncMock()
        mock_standalone.info = AsyncMock(return_value={"cluster_enabled": 1})
        mock_cluster = MagicMock()

        with (
            patch(
                "port_ocean.consumers.redis_client.Redis.from_url",
                return_value=mock_standalone,
            ) as mock_from_url,
            patch(
                "port_ocean.consumers.redis_client.RedisCluster.from_url",
                return_value=mock_cluster,
            ) as mock_cluster_from_url,
        ):
            client = await create_redis_client(
                "rediss://localhost:6379",
                decode_responses=True,
            )

        assert client is mock_cluster
        mock_from_url.assert_called_once_with(
            "rediss://localhost:6379",
            decode_responses=True,
        )
        mock_standalone.aclose.assert_awaited_once()
        mock_cluster_from_url.assert_called_once_with(
            "rediss://localhost:6379",
            decode_responses=True,
        )

    @pytest.mark.asyncio
    async def test_closes_probe_client_when_detection_fails(self) -> None:
        mock_standalone = AsyncMock()
        mock_standalone.info = AsyncMock(side_effect=ConnectionError("refused"))

        with (
            patch(
                "port_ocean.consumers.redis_client.Redis.from_url",
                return_value=mock_standalone,
            ),
            patch("port_ocean.consumers.redis_client.logger.exception") as mock_log,
            pytest.raises(ConnectionError, match="refused"),
        ):
            await create_redis_client("redis://localhost:6379")

        mock_standalone.aclose.assert_awaited_once()
        mock_log.assert_called_once()
        assert mock_log.call_args.args[0] == "Failed to connect to Redis"


class TestCalculateExponentialBackoffSeconds:
    def test_returns_initial_backoff_for_first_retry(self) -> None:
        assert (
            calculate_exponential_backoff_seconds(
                0,
                initial_backoff_seconds=1.0,
                exponential_base=2.0,
            )
            == 1.0
        )

    def test_applies_exponential_growth(self) -> None:
        assert (
            calculate_exponential_backoff_seconds(
                2,
                initial_backoff_seconds=1.0,
                exponential_base=2.0,
            )
            == 4.0
        )


class TestCreateRedisClientWithRetry:
    @pytest.mark.asyncio
    async def test_retries_until_connection_succeeds(self) -> None:
        mock_standalone = AsyncMock()
        mock_standalone.info = AsyncMock(return_value={"cluster_enabled": 0})
        connect_calls = 0

        def connect_side_effect(*_args: object, **_kwargs: object) -> AsyncMock:
            nonlocal connect_calls
            connect_calls += 1
            if connect_calls < 3:
                raise ConnectionError("refused")
            return mock_standalone

        with (
            patch(
                "port_ocean.consumers.redis_client.Redis.from_url",
                side_effect=connect_side_effect,
            ),
            patch(
                "port_ocean.consumers.redis_client.asyncio.sleep",
                new_callable=AsyncMock,
            ) as mock_sleep,
        ):
            client = await create_redis_client_with_retry(
                "redis://localhost:6379",
                max_retries=5,
                initial_backoff_seconds=1.0,
                exponential_base=2.0,
            )

        assert client is mock_standalone
        assert connect_calls == 3
        mock_sleep.assert_has_awaits([call(1.0), call(2.0)])

    @pytest.mark.asyncio
    async def test_raises_after_exhausting_retries(self) -> None:
        mock_standalone = AsyncMock()
        mock_standalone.info = AsyncMock(side_effect=ConnectionError("refused"))

        with (
            patch(
                "port_ocean.consumers.redis_client.Redis.from_url",
                return_value=mock_standalone,
            ),
            patch(
                "port_ocean.consumers.redis_client.asyncio.sleep",
                new_callable=AsyncMock,
            ) as mock_sleep,
            patch("port_ocean.consumers.redis_client.logger.exception") as mock_log,
            pytest.raises(ConnectionError, match="refused"),
        ):
            await create_redis_client_with_retry(
                "redis://localhost:6379",
                max_retries=2,
                initial_backoff_seconds=1.0,
                exponential_base=2.0,
            )

        assert mock_sleep.await_count == 2
        mock_log.assert_called_once()
        assert (
            mock_log.call_args.args[0]
            == "Failed to connect to Redis after exhausting startup retries"
        )
