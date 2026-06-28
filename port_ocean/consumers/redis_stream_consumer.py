import asyncio
import base64
import json
import os
import socket
import tempfile
import time
from collections.abc import Awaitable, Callable
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
from port_ocean.consumers.pel_requeue_worker import PELRequeueWorker
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

        self._pel_worker = PELRequeueWorker(
            redis=self._redis,
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
            pod_id=self._consumer_name,
            stuck_timeout_ms=self._settings.pel_stuck_timeout_seconds * 1000,
            max_requeue_count=self._settings.pel_max_requeue_count,
            scan_interval_seconds=self._settings.pel_scan_interval_seconds,
            leader_ttl_ms=self._settings.leader_election_ttl_ms,
            leader_heartbeat_seconds=self._settings.leader_election_heartbeat_seconds,
            election_retry_seconds=self._settings.leader_election_retry_seconds,
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
        await self._redis.xack(self._stream_key, self._consumer_group, message_id)

    def _require_redis(self) -> Redis:
        if self._redis is None:
            raise RuntimeError(
                "Redis stream consumer has not been started or has been stopped"
            )
        return self._redis

    async def _ensure_consumer_group(self) -> None:
        redis = self._require_redis()
        try:
            await redis.xgroup_create(
                self._stream_key,
                self._consumer_group,
                id="$",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

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
            except Exception as error:
                logger.exception(
                    "Unexpected error in Redis stream read loop",
                    error=str(error),
                )

    async def _handle_message(self, message_id: str, fields: dict[str, str]) -> None:
        start_time = time.monotonic()
        webhook_path: str | None = None
        try:
            raw_webhook_path = fields.get("webhookPath")
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
                message_id=message_id,
                error=str(error),
            )
        finally:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "Redis stream message processed",
                message_id=message_id,
                webhook_path=webhook_path,
                elapsed_ms=elapsed_ms,
            )
            await self._ack(message_id)

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
