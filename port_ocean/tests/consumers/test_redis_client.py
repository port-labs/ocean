from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.consumers.redis_client import (
    create_redis_client,
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
