import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.live_events_stream_key import (
    resolve_live_events_stream_key_from_base_url,
)
from port_ocean.consumers.redis_stream_consumer import RedisStreamConsumer


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

    def test_raises_when_live_events_segment_missing(self) -> None:
        with pytest.raises(ValueError, match="/live-events/\\{uuid\\}"):
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


class TestRedisStreamConsumer:
    def test_parse_json_object_field_handles_double_encoded_json(self) -> None:
        inner = {"action": "opened", "pull_request": {"number": 1}}
        fields = {"payload": json.dumps(json.dumps(inner))}

        assert RedisStreamConsumer._parse_json_object_field(fields, "payload") == inner

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
