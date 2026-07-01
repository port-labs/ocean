import asyncio
import base64
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from redis.asyncio.connection import SSLConnection
from redis.exceptions import ResponseError

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.live_events_stream_key import (
    resolve_live_events_stream_key_from_base_url,
)
from port_ocean.exceptions.live_events import (
    InvalidLiveEventsRedisStreamFieldError,
    LiveEventsUuidNotFoundError,
    MissingLiveEventsBaseUrlError,
)
from port_ocean.consumers.pel_requeue import PELRequeueWorker
from port_ocean.consumers.redis_stream_consumer import RedisStreamConsumer
from port_ocean.core.handlers.webhook.webhook_event import WebhookRequestAdapter


class TestResolveLiveEventsStreamKey:
    def test_extracts_uuid_from_base_url(self) -> None:
        base_url = (
            "https://working-dual-integrated-felt.trycloudflare.com"
            "/live-events/1111111/webhookkkk"
        )

        assert resolve_live_events_stream_key_from_base_url(base_url) == (
            "1111111/live-events/raw/event-stream"
        )

    def test_extracts_uuid_without_trailing_path(self) -> None:
        base_url = "https://host.example.com/live-events/abc-123"

        assert resolve_live_events_stream_key_from_base_url(base_url) == (
            "abc-123/live-events/raw/event-stream"
        )

    def test_raises_when_base_url_missing(self) -> None:
        with pytest.raises(MissingLiveEventsBaseUrlError):
            resolve_live_events_stream_key_from_base_url("")

    def test_raises_when_live_events_segment_missing(self) -> None:
        with pytest.raises(
            LiveEventsUuidNotFoundError, match="/live-events/\\{uuid\\}"
        ):
            resolve_live_events_stream_key_from_base_url("https://host.example.com")


@pytest.fixture
def redis_settings() -> LiveEventsRedisSettings:
    return LiveEventsRedisSettings(
        url="redis://localhost:6379",
        block_ms=100,
    )


@pytest.fixture
def mock_ocean_config() -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.config.integration.type = "test"
    mock_ocean.config.integration.identifier = "integration"
    return mock_ocean


def _pem_b64(content: str) -> str:
    return base64.b64encode(content.encode()).decode()


class TestRedisStreamConsumerConnection:
    def test_redis_client_kwargs_includes_username_and_password(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            username="redis-user",
            password="redis-pass",
        )

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )

        assert consumer._redis_client_kwargs() == {
            "decode_responses": True,
            "username": "redis-user",
            "password": "redis-pass",
        }

    def test_redis_client_kwargs_includes_tls_material(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        ca_pem = "-----BEGIN CERTIFICATE-----\nca\n-----END CERTIFICATE-----"
        cert_pem = "-----BEGIN CERTIFICATE-----\ncert\n-----END CERTIFICATE-----"
        key_pem = "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----"
        settings = LiveEventsRedisSettings(
            url="rediss://localhost:6379",
            enable_tls=True,
            ca=_pem_b64(ca_pem),
            cert=_pem_b64(cert_pem),
            private_key=_pem_b64(key_pem),
        )

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )

        kwargs = consumer._redis_client_kwargs()

        assert kwargs["connection_class"] is SSLConnection
        assert kwargs["ssl_ca_data"] == ca_pem
        assert kwargs["ssl_certfile"] == consumer._ssl_cert_file
        assert kwargs["ssl_keyfile"] == consumer._ssl_key_file
        with open(kwargs["ssl_certfile"], encoding="utf-8") as cert_file:
            assert cert_file.read() == cert_pem
        with open(kwargs["ssl_keyfile"], encoding="utf-8") as key_file:
            assert key_file.read() == key_pem

        consumer._cleanup_tls_files()

    def test_redis_client_kwargs_cleans_up_previous_tls_files_on_reconnect(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="rediss://localhost:6379",
            enable_tls=True,
            cert=_pem_b64(
                "-----BEGIN CERTIFICATE-----\ncert\n-----END CERTIFICATE-----"
            ),
            private_key=_pem_b64(
                "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----"
            ),
        )

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis_client_kwargs()
            old_cert_path = consumer._ssl_cert_file
            old_key_path = consumer._ssl_key_file

            consumer._redis_client_kwargs()

        assert old_cert_path is not None
        assert old_key_path is not None
        assert not os.path.exists(old_cert_path)
        assert not os.path.exists(old_key_path)

        consumer._cleanup_tls_files()

    def test_redis_client_kwargs_uses_tls_when_enabled(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="rediss://localhost:6379",
            enable_tls=True,
        )

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )

        kwargs = consumer._redis_client_kwargs()

        assert kwargs["connection_class"] is SSLConnection

    def test_redis_client_kwargs_rejects_mismatched_tls_url_scheme(self) -> None:
        with pytest.raises(ValueError, match="rediss://"):
            LiveEventsRedisSettings(url="rediss://localhost:6379")

        with pytest.raises(ValueError, match="rediss://"):
            LiveEventsRedisSettings(
                url="redis://localhost:6379",
                enable_tls=True,
            )

    @pytest.mark.asyncio
    async def test_stop_cleans_up_tls_files(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="rediss://localhost:6379",
            enable_tls=True,
            cert=_pem_b64(
                "-----BEGIN CERTIFICATE-----\ncert\n-----END CERTIFICATE-----"
            ),
            private_key=_pem_b64(
                "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----"
            ),
        )

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis_client_kwargs()
            cert_path = consumer._ssl_cert_file
            key_path = consumer._ssl_key_file

            consumer._redis = AsyncMock()
            consumer._read_task = None
            await consumer.stop()

        assert cert_path is not None
        assert key_path is not None
        assert not os.path.exists(cert_path)
        assert not os.path.exists(key_path)

    @pytest.mark.asyncio
    async def test_read_loop_uses_configured_read_count(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            read_count=25,
            block_ms=100,
        )
        mock_redis = AsyncMock()

        async def stop_after_first_read(**_kwargs: object) -> list[object]:
            consumer._is_running = False
            return []

        mock_redis.xreadgroup = AsyncMock(side_effect=stop_after_first_read)

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            consumer._is_running = True

            await consumer._read_loop()

        mock_redis.xreadgroup.assert_awaited_once()
        assert mock_redis.xreadgroup.await_args.kwargs["count"] == 25

    @pytest.mark.asyncio
    async def test_read_loop_recreates_consumer_group_when_stream_missing(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            block_ms=100,
        )
        mock_redis = AsyncMock()
        read_calls = 0

        async def read_side_effect(**_kwargs: object) -> list[object]:
            nonlocal read_calls
            read_calls += 1
            if read_calls == 1:
                raise ResponseError(
                    "NOGROUP No such key 'stream' or consumer group 'test.integration'"
                )
            consumer._is_running = False
            return []

        mock_redis.xreadgroup = AsyncMock(side_effect=read_side_effect)

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            consumer._is_running = True
            consumer._ensure_consumer_group = AsyncMock()  # type: ignore[method-assign]

            await consumer._read_loop()

        consumer._ensure_consumer_group.assert_awaited_once()
        assert mock_redis.xreadgroup.await_count == 2


class TestRedisStreamConsumerGroupCreation:
    @pytest.mark.asyncio
    async def test_sets_ttl_when_consumer_creates_stream(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            stream_ttl_seconds=3600,
        )
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            await consumer._ensure_consumer_group()

        mock_redis.expire.assert_awaited_once_with("stream", 3600)

    @pytest.mark.asyncio
    async def test_skips_ttl_when_stream_already_exists(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            stream_ttl_seconds=3600,
        )
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            await consumer._ensure_consumer_group()

        mock_redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_ttl_when_disabled(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            stream_ttl_seconds=None,
        )
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            await consumer._ensure_consumer_group()

        mock_redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_start_id_zero_when_stream_already_exists(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(url="redis://localhost:6379")
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            await consumer._ensure_consumer_group()

        assert mock_redis.xgroup_create.await_args.kwargs["id"] == "0"
        mock_redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_start_id_dollar_when_creating_empty_stream(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(url="redis://localhost:6379")
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            await consumer._ensure_consumer_group()

        assert mock_redis.xgroup_create.await_args.kwargs["id"] == "$"
        mock_redis.expire.assert_awaited_once_with("stream", 3600)

    @pytest.mark.asyncio
    async def test_skips_ttl_when_consumer_group_already_exists(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            stream_ttl_seconds=3600,
        )
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.xgroup_create = AsyncMock(
            side_effect=ResponseError("BUSYGROUP Consumer Group name already exists")
        )
        mock_redis.expire = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            consumer._redis = mock_redis
            await consumer._ensure_consumer_group()

        mock_redis.expire.assert_not_awaited()


class TestRedisStreamConsumerPelWorkerLifecycle:
    @pytest.mark.asyncio
    async def test_start_starts_pel_worker_when_enabled(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            pel_requeue_worker_enabled=True,
        )
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock()
        mock_pel_worker = AsyncMock()

        with (
            patch(
                "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
            ),
            patch(
                "port_ocean.consumers.redis_stream_consumer.Redis.from_url",
                return_value=mock_redis,
            ),
            patch(
                "port_ocean.consumers.redis_stream_consumer.PELRequeueWorker",
                return_value=mock_pel_worker,
            ) as mock_pel_worker_cls,
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            await consumer.start()

            mock_pel_worker_cls.assert_called_once()
            mock_pel_worker.start.assert_awaited_once()
            assert consumer._pel_worker is mock_pel_worker

            await consumer.stop()

            mock_pel_worker.stop.assert_awaited_once()
            assert consumer._pel_worker is None
            mock_redis.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_skips_pel_worker_when_disabled(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            pel_requeue_worker_enabled=False,
        )
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock()

        with (
            patch(
                "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
            ),
            patch(
                "port_ocean.consumers.redis_stream_consumer.Redis.from_url",
                return_value=mock_redis,
            ),
            patch(
                "port_ocean.consumers.redis_stream_consumer.PELRequeueWorker",
            ) as mock_pel_worker_cls,
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )
            await consumer.start()

            mock_pel_worker_cls.assert_not_called()
            assert consumer._pel_worker is None

            await consumer.stop()

            assert consumer._pel_worker is None
            mock_redis.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pel_worker_requeues_while_handler_still_processing(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        """If processing exceeds stuck_timeout, PEL worker can requeue while the
        original handler is still in flight — enabling duplicate delivery."""
        handler_entered = asyncio.Event()
        release_handler = asyncio.Event()

        async def slow_on_message(path: str, event: object) -> None:
            handler_entered.set()
            await release_handler.wait()

        settings = LiveEventsRedisSettings(
            url="redis://localhost:6379",
            pel_stuck_timeout_seconds=60,
        )
        message_id = "1700000000000-0"
        fields = {
            "webhookPath": "integration/webhook",
            "payload": json.dumps({}),
            "headers": json.dumps({}),
        }

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1700000000001-0")
        mock_redis.xack = AsyncMock(return_value=1)

        @asynccontextmanager
        async def fake_pipeline(
            *_args: object, **_kwargs: object
        ) -> AsyncIterator[AsyncMock]:
            pipe = AsyncMock()
            pipe.xadd = mock_redis.xadd
            pipe.xack = mock_redis.xack
            pipe.execute = AsyncMock(return_value=["1700000000001-0", 1])
            yield pipe

        mock_redis.pipeline = fake_pipeline
        mock_redis.xautoclaim = AsyncMock(
            return_value=("0-0", [(message_id, fields)], [])
        )

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=slow_on_message,
                registered_paths={"/webhook"},
            )
            consumer._redis = mock_redis

            handle_task = asyncio.create_task(
                consumer._handle_message(message_id, fields)
            )
            await handler_entered.wait()

            pel_worker = PELRequeueWorker(
                mock_redis,
                redis_settings=settings,
                stream_key="stream",
                consumer_group=consumer._consumer_group,
            )
            await pel_worker._scan_and_requeue()

            mock_redis.xadd.assert_awaited_once()
            requeued_fields: dict[str, str] = mock_redis.xadd.await_args.args[1]
            assert requeued_fields["requeue_count"] == "1"

            release_handler.set()
            await handle_task

            assert mock_redis.xack.await_count >= 1


class TestRedisStreamConsumer:
    def test_parse_raw_json_to_dict_parses_json_object(self) -> None:
        inner = {"action": "opened", "pull_request": {"number": 1}}

        assert (
            RedisStreamConsumer._parse_raw_json_to_dict(json.dumps(inner), "payload")
            == inner
        )

    def test_parse_raw_json_to_dict_raises_for_non_object_json(self) -> None:
        with pytest.raises(InvalidLiveEventsRedisStreamFieldError, match="payload"):
            RedisStreamConsumer._parse_raw_json_to_dict(
                json.dumps(["not", "an", "object"]), "payload"
            )

    def test_normalize_headers_lowercases_keys(self) -> None:
        assert RedisStreamConsumer._normalize_headers(
            {"X-GitHub-Event": "push", "Content-Type": "application/json"}
        ) == {
            "x-github-event": "push",
            "content-type": "application/json",
        }

    def test_normalize_webhook_path(self) -> None:
        assert RedisStreamConsumer._normalize_webhook_path("/webhook") == "/webhook"
        assert (
            RedisStreamConsumer._normalize_webhook_path("integration/webhook")
            == "/webhook"
        )
        assert (
            RedisStreamConsumer._normalize_webhook_path("/integration/webhook")
            == "/webhook"
        )
        assert (
            RedisStreamConsumer._normalize_webhook_path(
                "/live-events/1111111/integration/webhook"
            )
            == "/webhook"
        )
        assert (
            RedisStreamConsumer._normalize_webhook_path(
                "integration/webhook/monitor-events"
            )
            == "/webhook/monitor-events"
        )

    def test_parse_queued_at_from_unix_nanoseconds(self) -> None:
        queued_at = "1700000000000000000"

        assert RedisStreamConsumer._parse_queued_at(
            queued_at
        ) == datetime.fromtimestamp(1700000000, tz=timezone.utc)

    def test_parse_queued_at_from_unix_nanoseconds_with_fraction(self) -> None:
        queued_at = "1700000000500000000"

        assert RedisStreamConsumer._parse_queued_at(
            queued_at
        ) == datetime.fromtimestamp(1700000000.5, tz=timezone.utc)

    def test_parse_queued_at_returns_none_when_missing(self) -> None:
        assert RedisStreamConsumer._parse_queued_at(None) is None
        assert RedisStreamConsumer._parse_queued_at("") is None

    def test_parse_queued_at_returns_none_for_invalid_timestamp(self) -> None:
        assert RedisStreamConsumer._parse_queued_at("not-a-timestamp") is None

    def test_time_since_queued_ms(self) -> None:
        queued_time = datetime.fromtimestamp(1700000000, tz=timezone.utc)
        consumed_at = datetime.fromtimestamp(1700000001.5, tz=timezone.utc)

        assert (
            RedisStreamConsumer._time_since_queued_ms(queued_time, now=consumed_at)
            == 1500.0
        )

    def test_time_since_queued_ms_clamps_negative_delta_to_zero(self) -> None:
        queued_time = datetime.fromtimestamp(1700000001.5, tz=timezone.utc)
        consumed_at = datetime.fromtimestamp(1700000000, tz=timezone.utc)

        with patch(
            "port_ocean.consumers.redis_stream_consumer.logger.warning"
        ) as mock_warning:
            assert (
                RedisStreamConsumer._time_since_queued_ms(queued_time, now=consumed_at)
                == 0.0
            )

        mock_warning.assert_called_once_with(
            "queuedAt is in the future relative to consumer clock",
            queued_time=queued_time.isoformat(),
            reference_time=consumed_at.isoformat(),
            delta_ms=-1500.0,
        )

    def test_time_since_queued_ms_returns_none_when_queued_time_missing(self) -> None:
        assert RedisStreamConsumer._time_since_queued_ms(None) is None

    @pytest.mark.asyncio
    async def test_handle_message_logs_time_until_consumed(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        path = "/webhook"
        on_message = AsyncMock()

        with (
            patch(
                "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
            ),
            patch(
                "port_ocean.consumers.redis_stream_consumer.logger.info"
            ) as mock_logger_info,
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths={path},
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            with (
                patch.object(
                    RedisStreamConsumer,
                    "_parse_queued_at",
                    return_value=datetime.fromtimestamp(1700000000, tz=timezone.utc),
                ),
                patch.object(
                    RedisStreamConsumer,
                    "_time_since_queued_ms",
                    side_effect=[2000.0, 2500.0],
                ),
            ):
                await consumer._handle_message(
                    "1700000000000-0",
                    {
                        "payload": json.dumps({}),
                        "headers": json.dumps({}),
                        "webhookPath": "integration/webhook",
                        "queuedAt": "1700000000000000000",
                    },
                )

        mock_logger_info.assert_any_call(
            "Redis stream message consumed",
            stream_key="1111111/live-events/raw/event-stream",
            message_id="1700000000000-0",
            time_until_consumed_ms=2000.0,
        )
        mock_logger_info.assert_any_call(
            "Redis stream message processed",
            stream_key="1111111/live-events/raw/event-stream",
            message_id="1700000000000-0",
            webhook_path="/webhook",
            elapsed_ms=ANY,
            time_until_acked_ms=2500.0,
        )

    @pytest.mark.asyncio
    async def test_handle_message_logs_invalid_queued_at_once(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        path = "/webhook"
        on_message = AsyncMock()

        with (
            patch(
                "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
            ),
            patch(
                "port_ocean.consumers.redis_stream_consumer.logger.warning"
            ) as mock_logger_warning,
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths={path},
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            await consumer._handle_message(
                "1700000000000-0",
                {
                    "payload": json.dumps({}),
                    "headers": json.dumps({}),
                    "webhookPath": "integration/webhook",
                    "queuedAt": "not-a-timestamp",
                },
            )

        mock_logger_warning.assert_called_once_with(
            "Invalid queuedAt in Redis stream message",
            stream_key="1111111/live-events/raw/event-stream",
            queued_at="not-a-timestamp",
        )

    @pytest.mark.asyncio
    async def test_handle_message_invokes_handler_for_registered_path(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        path = "/webhook"
        on_message = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths={path},
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            await consumer._handle_message(
                "1700000000000-0",
                {
                    "payload": json.dumps({"hello": "world"}),
                    "headers": json.dumps({"x-github-event": "push"}),
                    "webhookPath": "integration/webhook",
                },
            )

        on_message.assert_awaited_once()
        assert on_message.await_args is not None
        assert on_message.await_args.args[0] == path
        assert on_message.await_args.args[1].payload == {"hello": "world"}
        assert on_message.await_args.args[1].headers == {"x-github-event": "push"}
        assert on_message.await_args.args[1].trace_id
        consumer._ack.assert_awaited_once_with("1700000000000-0")

    @pytest.mark.asyncio
    async def test_handle_message_acks_unknown_path_without_handler(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        on_message = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths=set(),
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            await consumer._handle_message(
                "1700000000000-0",
                {
                    "payload": json.dumps({}),
                    "headers": json.dumps({}),
                    "webhookPath": "/unknown",
                },
            )

        on_message.assert_not_called()
        consumer._ack.assert_awaited_once_with("1700000000000-0")

    @pytest.mark.asyncio
    async def test_handle_message_acks_when_webhook_path_missing(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        on_message = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths={"/webhook"},
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            await consumer._handle_message(
                "1700000000000-0",
                {
                    "payload": json.dumps({}),
                    "headers": json.dumps({}),
                },
            )

        on_message.assert_not_called()
        consumer._ack.assert_awaited_once_with("1700000000000-0")

    @pytest.mark.asyncio
    async def test_handle_message_sets_original_request_from_payload(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        path = "/webhook"
        on_message = AsyncMock()
        raw_payload = json.dumps({"action": "opened"})

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths={path},
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            await consumer._handle_message(
                "1700000000000-0",
                {
                    "payload": raw_payload,
                    "headers": json.dumps({"x-hub-signature-256": "sha256=abc"}),
                    "webhookPath": "integration/webhook",
                },
            )

        on_message.assert_awaited_once()
        assert on_message.await_args is not None
        event = on_message.await_args.args[1]
        assert isinstance(event._original_request, WebhookRequestAdapter)
        assert await event._original_request.body() == raw_payload.encode("utf-8")
        assert event._original_request.headers["x-hub-signature-256"] == "sha256=abc"

    @pytest.mark.asyncio
    async def test_handle_message_original_request_is_none_when_payload_absent(
        self,
        redis_settings: LiveEventsRedisSettings,
        mock_ocean_config: MagicMock,
    ) -> None:
        path = "/webhook"
        on_message = AsyncMock()

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=redis_settings,
                stream_key="1111111/live-events/raw/event-stream",
                on_message=on_message,
                registered_paths={path},
            )
            consumer._ack = AsyncMock()  # type: ignore[method-assign]

            await consumer._handle_message(
                "1700000000000-0",
                {
                    "headers": json.dumps({}),
                    "webhookPath": "integration/webhook",
                },
            )

        on_message.assert_awaited_once()
        assert on_message.await_args is not None
        event = on_message.await_args.args[1]
        assert event._original_request is None
