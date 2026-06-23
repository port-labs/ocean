import base64
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio.connection import SSLConnection

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.live_events_stream_key import (
    resolve_live_events_stream_key_from_base_url,
)
from port_ocean.exceptions.live_events import (
    InvalidLiveEventsRedisStreamFieldError,
    LiveEventsUuidNotFoundError,
    MissingLiveEventsBaseUrlError,
)
from port_ocean.consumers.redis_stream_consumer import (
    RedisStreamConsumer,
    _WebhookRequestAdapter,
)


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
        consumer_group="test.integration",
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
            url="redis://localhost:6379",
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

    def test_redis_client_kwargs_does_not_enable_tls_for_rediss_url_without_flag(
        self,
        mock_ocean_config: MagicMock,
    ) -> None:
        settings = LiveEventsRedisSettings(url="rediss://localhost:6379")

        with patch(
            "port_ocean.consumers.redis_stream_consumer.ocean", mock_ocean_config
        ):
            consumer = RedisStreamConsumer(
                redis_settings=settings,
                stream_key="stream",
                on_message=AsyncMock(),
            )

        assert consumer._redis_client_kwargs() == {"decode_responses": True}

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


class TestRedisStreamConsumer:
    def test_parse_json_object_field_handles_double_encoded_json(self) -> None:
        inner = {"action": "opened", "pull_request": {"number": 1}}
        fields = {"payload": json.dumps(json.dumps(inner))}

        assert RedisStreamConsumer._parse_json_object_field(fields, "payload") == inner

    def test_parse_json_object_field_raises_for_non_object_json(self) -> None:
        fields = {"payload": json.dumps(["not", "an", "object"])}

        with pytest.raises(InvalidLiveEventsRedisStreamFieldError, match="payload"):
            RedisStreamConsumer._parse_json_object_field(fields, "payload")

    def test_get_field_is_case_insensitive(self) -> None:
        fields = {"Payload": "{}", "webhookPath": "/webhook"}

        assert RedisStreamConsumer._get_field(fields, "payload") == "{}"
        assert RedisStreamConsumer._get_field(fields, "webhookPath") == "/webhook"

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
        assert isinstance(event._original_request, _WebhookRequestAdapter)
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


class TestWebhookRequestAdapter:
    @pytest.mark.asyncio
    async def test_body_returns_raw_bytes(self) -> None:
        raw = b'{"action":"opened"}'
        adapter = _WebhookRequestAdapter(raw_body=raw, headers={})
        assert await adapter.body() == raw

    @pytest.mark.asyncio
    async def test_body_is_idempotent(self) -> None:
        raw = b'{"x":1}'
        adapter = _WebhookRequestAdapter(raw_body=raw, headers={})
        assert await adapter.body() == await adapter.body()

    def test_headers_accessible(self) -> None:
        headers = {
            "x-hub-signature-256": "sha256=abc",
            "content-type": "application/json",
        }
        adapter = _WebhookRequestAdapter(raw_body=b"", headers=headers)
        assert adapter.headers == headers
