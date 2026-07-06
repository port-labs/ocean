import asyncio
import base64
import json
import os
import socket
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio.connection import SSLConnection
from redis.exceptions import ResponseError

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.abstract_live_events_consumer import (
    AbstractLiveEventsConsumer,
)
from port_ocean.consumers.pel_requeue import PELRequeueWorker
from port_ocean.consumers.redis_stream_utils import is_missing_stream_or_group_error
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.live_events import InvalidLiveEventsRedisStreamFieldError
from port_ocean.core.handlers.webhook.webhook_event import (
    LiveEventTimestamp,
    WebhookEvent,
    WebhookRequestAdapter,
)

_INTEGRATION_PATH_PREFIX = "/integration/"


OnStreamMessage = Callable[[str, WebhookEvent], Awaitable[None]]


class RedisStreamConsumer(AbstractLiveEventsConsumer):
    """Consumes live events directly from a Redis stream and invokes a handler."""

    def __init__(
        self,
        redis_settings: LiveEventsRedisSettings,
        stream_key: str,
        on_message: OnStreamMessage,
        *,
        registered_paths: set[str] | None = None,
    ) -> None:
        self._settings = redis_settings
        self._stream_key = stream_key
        self._on_message = on_message
        self._consumer_group = self._resolve_consumer_group()
        self._registered_paths = registered_paths or set()
        self._redis: Redis | None = None
        self._ssl_cert_file: str | None = None
        self._ssl_key_file: str | None = None
        self._is_running = False
        self._read_task: asyncio.Task[None] | None = None
        self._consumer_name = (
            f"{ocean.config.integration.identifier}-{socket.gethostname()}"
        )
        self._pel_worker: PELRequeueWorker | None = None

    def _resolve_consumer_group(self) -> str:
        integration = ocean.config.integration
        return f"{integration.type}.{integration.identifier}"

    def _decode_base64_pem(self, value: str) -> str:
        return base64.b64decode(value).decode()

    def _materialize_client_tls_files(self) -> tuple[str | None, str | None]:
        if not self._settings.cert or not self._settings.private_key:
            return None, None

        cert_pem = self._decode_base64_pem(self._settings.cert)
        key_pem = self._decode_base64_pem(self._settings.private_key)

        cert_fd, cert_path = tempfile.mkstemp(suffix=".pem", prefix="redis-cert-")
        key_fd, key_path = tempfile.mkstemp(suffix=".pem", prefix="redis-key-")
        with os.fdopen(cert_fd, "w") as cert_file:
            cert_file.write(cert_pem)
        with os.fdopen(key_fd, "w") as key_file:
            key_file.write(key_pem)

        self._ssl_cert_file = cert_path
        self._ssl_key_file = key_path
        return cert_path, key_path

    def _cleanup_tls_files(self) -> None:
        for path in (self._ssl_cert_file, self._ssl_key_file):
            if path and os.path.exists(path):
                os.unlink(path)
        self._ssl_cert_file = None
        self._ssl_key_file = None

    def _redis_client_kwargs(self) -> dict[str, Any]:
        """Connection kwargs for redis-py, including auth and TLS for cloud Redis."""
        self._cleanup_tls_files()
        kwargs: dict[str, Any] = {"decode_responses": True}
        if self._settings.username:
            kwargs["username"] = self._settings.username
        if self._settings.password is not None:
            kwargs["password"] = self._settings.password

        if not self._settings.enable_tls:
            return kwargs

        kwargs["connection_class"] = SSLConnection
        if self._settings.ca:
            kwargs["ssl_ca_data"] = self._decode_base64_pem(self._settings.ca)

        cert_path, key_path = self._materialize_client_tls_files()
        if cert_path and key_path:
            kwargs["ssl_certfile"] = cert_path
            kwargs["ssl_keyfile"] = key_path

        return kwargs

    async def start(self) -> None:
        self._redis = Redis.from_url(self._settings.url, **self._redis_client_kwargs())
        await self._ensure_consumer_group()
        self._is_running = True
        self._read_task = asyncio.create_task(self._read_loop())

        if self._settings.pel_requeue_worker_enabled:
            self._pel_worker = PELRequeueWorker(
                redis=self._redis,
                redis_settings=self._settings,
                stream_key=self._stream_key,
                consumer_group=self._consumer_group,
            )
            await self._pel_worker.start()

        logger.info(
            "Started Redis stream consumer",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
            consumer_name=self._consumer_name,
        )

    async def stop(self) -> None:
        self._is_running = False
        if self._read_task is not None:
            self._read_task.cancel()
            await asyncio.gather(self._read_task, return_exceptions=True)
            self._read_task = None
        if self._pel_worker is not None:
            await self._pel_worker.stop()
            self._pel_worker = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        self._cleanup_tls_files()

    async def _ack(self, message_id: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.xack(self._stream_key, self._consumer_group, message_id)
        except ResponseError as error:
            if not is_missing_stream_or_group_error(error):
                raise
            logger.warning(
                "Redis stream or consumer group missing during ack, recreating",
                stream_key=self._stream_key,
                message_id=message_id,
                error=str(error),
            )
            await self._ensure_consumer_group()

    def _require_redis(self) -> Redis:
        if self._redis is None:
            raise RuntimeError(
                "Redis stream consumer has not been started or has been stopped"
            )
        return self._redis

    async def _ensure_consumer_group(self) -> None:
        redis = self._require_redis()
        stream_existed = bool(await redis.exists(self._stream_key))
        consumer_group_created = False
        try:
            await redis.xgroup_create(
                self._stream_key,
                self._consumer_group,
                id="$",
                mkstream=True,
            )
            consumer_group_created = True
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

        if (
            consumer_group_created
            and not stream_existed
            and self._settings.stream_ttl_seconds is not None
        ):
            await redis.expire(self._stream_key, self._settings.stream_ttl_seconds)
            logger.info(
                "Set TTL on newly created Redis stream",
                stream_key=self._stream_key,
                stream_ttl_seconds=self._settings.stream_ttl_seconds,
            )

    async def _recover_missing_stream(self) -> None:
        logger.warning(
            "Redis stream or consumer group missing, recreating",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
        )
        await self._ensure_consumer_group()

    async def _read_loop(self) -> None:
        redis = self._require_redis()

        while self._is_running:
            try:
                response = await redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={self._stream_key: ">"},
                    count=self._settings.read_count,
                    block=self._settings.block_ms,
                )
                if not response:
                    continue

                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        await self._handle_message(message_id, fields)
            except asyncio.CancelledError:
                break
            except ResponseError as error:
                if is_missing_stream_or_group_error(error):
                    try:
                        await self._recover_missing_stream()
                    except Exception as recovery_error:
                        logger.exception(
                            "Failed to recreate Redis stream consumer group",
                            stream_key=self._stream_key,
                            error=str(recovery_error),
                        )
                else:
                    logger.exception(
                        "Unexpected Redis error in stream read loop",
                        stream_key=self._stream_key,
                        error=str(error),
                    )
            except Exception as error:
                logger.exception(
                    "Unexpected error in Redis stream read loop",
                    stream_key=self._stream_key,
                    error=str(error),
                )

    async def _handle_message(self, message_id: str, fields: dict[str, str]) -> None:
        start_time = time.monotonic()
        webhook_path: str | None = None
        queued_time = self._parse_queued_at(
            fields.get("queuedAt"), stream_key=self._stream_key
        )
        time_until_consumed_ms = self._time_since_queued_ms(queued_time)
        try:
            raw_webhook_path = fields.get("webhookPath")
            if not raw_webhook_path:
                logger.warning(
                    "Redis stream message missing webhookPath, acknowledging",
                    stream_key=self._stream_key,
                    message_id=message_id,
                )
                return

            webhook_path = self._normalize_webhook_path(raw_webhook_path)
            if webhook_path not in self._registered_paths:
                logger.warning(
                    "No processors registered for webhookPath, acknowledging",
                    stream_key=self._stream_key,
                    webhook_path=webhook_path,
                    message_id=message_id,
                )
                return

            raw_payload = fields.get("payload")
            payload = self._parse_raw_json_to_dict(raw_payload, "payload")
            headers = self._normalize_headers(
                self._parse_raw_json_to_dict(fields.get("headers"), "headers")
            )
            original_request = None
            if raw_payload is not None:
                original_request = WebhookRequestAdapter(
                    raw_body=raw_payload.encode("utf-8"),
                    headers=headers,
                )

            webhook_event = WebhookEvent(
                trace_id=str(uuid4()),
                payload=payload,
                headers=headers,
                original_request=original_request,
            )

            webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
            await self._on_message(webhook_path, webhook_event)
        except Exception as error:
            logger.exception(
                "Failed to handle Redis stream message",
                stream_key=self._stream_key,
                message_id=message_id,
                error=str(error),
            )
        finally:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            await self._ack(message_id)
            time_until_acked_ms = self._time_since_queued_ms(queued_time)
            logger.info(
                "Redis stream message processed",
                stream_key=self._stream_key,
                message_id=message_id,
                webhook_path=webhook_path,
                elapsed_ms=elapsed_ms,
                time_until_consumed_ms=time_until_consumed_ms,
                time_until_acked_ms=time_until_acked_ms,
            )

    @staticmethod
    def _parse_queued_at(
        queued_at: str | None,
        *,
        stream_key: str | None = None,
    ) -> datetime | None:
        if not queued_at:
            return None

        try:
            return datetime.fromtimestamp(
                float(queued_at) / 1_000_000_000, tz=timezone.utc
            )
        except (ValueError, OSError, OverflowError):
            logger.warning(
                "Invalid queuedAt in Redis stream message",
                stream_key=stream_key,
                queued_at=queued_at,
            )
            return None

    @staticmethod
    def _time_since_queued_ms(
        queued_time: datetime | None,
        *,
        now: datetime | None = None,
    ) -> float | None:
        if queued_time is None:
            return None

        reference_time = now or datetime.now(timezone.utc)
        delta_ms = (reference_time - queued_time).total_seconds() * 1000
        if delta_ms < 0:
            logger.warning(
                "queuedAt is in the future relative to consumer clock",
                queued_time=queued_time.isoformat(),
                reference_time=reference_time.isoformat(),
                delta_ms=round(delta_ms, 2),
            )
            return 0.0

        return round(delta_ms, 2)

    @staticmethod
    def _normalize_webhook_path(webhook_path: str) -> str:
        """Map ingestion HTTP paths to integration processor paths.

        Integrations register processors relative to the integration router
        (e.g. ``integration/webhook``).
        """
        path = f"/{webhook_path.strip('/')}"
        if _INTEGRATION_PATH_PREFIX in path:
            path = f"/{path.split(_INTEGRATION_PATH_PREFIX, 1)[1]}"
        return path

    @classmethod
    def _parse_raw_json_to_dict(
        cls, raw_value: str | None, field_name: str
    ) -> dict[str, Any]:
        if raw_value is None:
            return {}

        parsed: Any = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise InvalidLiveEventsRedisStreamFieldError(field_name)
        return parsed

    @staticmethod
    def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}
