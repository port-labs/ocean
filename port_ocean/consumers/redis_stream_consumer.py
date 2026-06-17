import asyncio
import json
import socket
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import (
    LiveEventTimestamp,
    WebhookEvent,
)

OnStreamMessage = Callable[[str, WebhookEvent], Awaitable[None]]


class RedisStreamConsumer:
    """Consumes live events directly from a Redis stream and invokes a handler."""

    def __init__(
        self,
        redis_settings: LiveEventsRedisSettings,
        stream_key: str,
        on_message: OnStreamMessage,
        *,
        consumer_group: str | None = None,
        registered_paths: set[str] | None = None,
    ) -> None:
        self._settings = redis_settings
        self._stream_key = stream_key
        self._on_message = on_message
        self._consumer_group = consumer_group or self._resolve_consumer_group()
        self._registered_paths = registered_paths or set()
        self._redis: Redis | None = None
        self._running = False
        self._read_task: asyncio.Task[None] | None = None
        self._consumer_name = (
            f"{ocean.config.integration.identifier}-{socket.gethostname()}"
        )

    def _resolve_consumer_group(self) -> str:
        integration = ocean.config.integration
        return f"{integration.type}.{integration.identifier}"

    async def start(self) -> None:
        self._redis = Redis.from_url(self._settings.url, decode_responses=True)
        await self._ensure_consumer_group()
        self._running = True
        self._read_task = asyncio.create_task(self._read_loop())

        logger.info(
            "Started Redis stream consumer",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
            consumer_name=self._consumer_name,
        )

    async def stop(self) -> None:
        self._running = False
        if self._read_task is not None:
            self._read_task.cancel()
            await asyncio.gather(self._read_task, return_exceptions=True)
            self._read_task = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _ack(self, message_id: str) -> None:
        if self._redis is None:
            return
        await self._redis.xack(self._stream_key, self._consumer_group, message_id)

    async def _ensure_consumer_group(self) -> None:
        assert self._redis is not None
        try:
            await self._redis.xgroup_create(
                self._stream_key,
                self._consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def _read_loop(self) -> None:
        assert self._redis is not None

        while self._running:
            try:
                response = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={self._stream_key: ">"},
                    count=10,
                    block=self._settings.block_ms,
                )
                if not response:
                    continue

                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        await self._handle_message(message_id, fields)
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.exception(
                    "Unexpected error in Redis stream read loop",
                    error=str(error),
                )
                await asyncio.sleep(1)

    async def _handle_message(self, message_id: str, fields: dict[str, str]) -> None:
        try:
            raw_webhook_path = self._get_field(fields, "webhookPath")
            if not raw_webhook_path:
                logger.warning(
                    "Redis stream message missing webhookPath, acknowledging",
                    message_id=message_id,
                )
                return

            webhook_path = self._normalize_webhook_path(raw_webhook_path)
            if webhook_path not in self._registered_paths:
                logger.warning(
                    "No processors registered for webhookPath, acknowledging",
                    webhook_path=webhook_path,
                    message_id=message_id,
                )
                return

            payload = self._parse_json_object_field(fields, "payload")
            headers = self._normalize_headers(
                self._parse_json_object_field(fields, "headers")
            )

            webhook_event = WebhookEvent(
                trace_id=str(uuid4()),
                payload=payload,
                headers=headers,
            )
            webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
            await self._on_message(webhook_path, webhook_event)
        except Exception as error:
            logger.exception(
                "Failed to handle Redis stream message",
                message_id=message_id,
                error=str(error),
            )
        finally:
            await self._ack(message_id)

    @staticmethod
    def _normalize_webhook_path(webhook_path: str) -> str:
        """Map ingestion HTTP paths to integration processor paths.

        Integrations register processors relative to the integration router
        (e.g. ``/webhook``), while ingestion forwards the public URL suffix
        (e.g. ``integration/webhook``).
        """
        path = f"/{webhook_path.strip('/')}"
        integration_marker = "/integration/"
        if integration_marker in path:
            path = f"/{path.split(integration_marker, 1)[1]}"
        return path

    @staticmethod
    def _get_field(fields: dict[str, str], field_name: str) -> str | None:
        for key, value in fields.items():
            if key.lower() == field_name.lower():
                return value
        return None

    @classmethod
    def _parse_json_object_field(
        cls, fields: dict[str, str], field_name: str
    ) -> dict[str, Any]:
        raw_value = cls._get_field(fields, field_name)
        if raw_value is None:
            return {}

        parsed: Any = json.loads(raw_value)
        while isinstance(parsed, str):
            parsed = json.loads(parsed)

        if not isinstance(parsed, dict):
            raise ValueError(
                f"Redis stream {field_name} field must contain a JSON object"
            )
        return parsed

    @staticmethod
    def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}
