"""Structured integration events reporter for the integ-service events ingest pipeline.

Posts KIND and BATCH lifecycle events during extraction so that customers/support
can observe incremental sync progress via the sync-status UI.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig
from port_ocean.version import __integration_version__

FLUSH_THRESHOLD = 10


@dataclass
class KindToBlueprint:
    kind: str
    blueprint: str
    kind_identifier: str

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "blueprint": self.blueprint,
            "kindIdentifier": self.kind_identifier,
        }


@dataclass
class ExtractMetrics:
    fetched: int = 0
    failed: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "extract": {
                "fetched": self.fetched,
                "failed": self.failed,
                "durationSeconds": round(self.duration_seconds, 3),
            }
        }


@dataclass
class BatchTimer:
    _start: float = field(default_factory=time.monotonic, init=False)

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start


def make_batch_id() -> str:
    return str(uuid4())


class IntegrationEventsReporter:
    """Reports structured integration events to integ-service during extraction.

    Events are buffered and flushed at FLUSH_THRESHOLD or explicitly.
    All operations are best-effort — failures never crash the sync.
    """

    def __init__(
        self,
        auth: PortAuthentication,
        integration_identifier: str,
        integration_type: str,
        integration_version: str,
    ) -> None:
        self._auth = auth
        self._integration_identifier = integration_identifier
        self._integration_type = integration_type
        self._integration_version = integration_version or __integration_version__
        self._http_client = OceanAsyncClient(
            timeout=10, retry_config=RetryConfig(retryable_methods=["POST"])
        )
        self._buffer: list[dict[str, Any]] = []
        self._events_ingest_url: str | None = None

    async def _get_events_ingest_url(self) -> str:
        if self._events_ingest_url is not None:
            return self._events_ingest_url

        from port_ocean.context.ocean import ocean

        log_url = (await ocean.port_client.get_log_attributes())["ingestUrl"]
        ingest_id = log_url.rsplit("/", 1)[-1]
        base_url = log_url.split("/logs/integration/")[0]
        self._events_ingest_url = f"{base_url}/events/ingestId/{ingest_id}"
        return self._events_ingest_url

    def _build_event(
        self,
        granularity: str,
        lifecycle: str,
        correlation_id: str,
        payload: dict[str, Any],
        event_id: str,
    ) -> dict[str, Any]:
        return {
            "id": event_id,
            "granularity": granularity,
            "lifecycle": lifecycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "OCEAN",
            "correlationId": correlation_id,
            "correlationKind": "INCREMENTAL_RESYNC",
            "integrationIdentifier": self._integration_identifier,
            "integrationType": self._integration_type,
            "integrationVersion": self._integration_version,
            "payload": payload,
        }

    async def _enqueue(self, event: dict[str, Any]) -> None:
        self._buffer.append(event)
        if len(self._buffer) >= FLUSH_THRESHOLD:
            await self.flush()

    async def _post(self, events: list[dict[str, Any]]) -> None:
        try:
            url = await self._get_events_ingest_url()
            headers = await self._auth.headers()
            resp = await self._http_client.post(url, headers=headers, json={"events": events})
            if resp.is_error:
                logger.warning("Integration events ingest error", status_code=resp.status_code)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Failed to post integration events", error=str(exc))

    async def flush(self) -> None:
        if not self._buffer:
            return
        events, self._buffer = self._buffer[:], []
        try:
            await self._post(events)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    # ── KIND ─────────────────────────────────────────────────────────────────

    async def report_kind_started(
        self, correlation_id: str, kind_to_blueprint: KindToBlueprint, kind_index: int | None = None
    ) -> None:
        payload: dict[str, Any] = {"kindToBlueprint": kind_to_blueprint.to_dict()}
        if kind_index is not None:
            payload["kindIndex"] = kind_index
        event_id = f"{correlation_id}#{kind_to_blueprint.kind_identifier}#KIND#STARTED"
        await self._enqueue(self._build_event("KIND", "STARTED", correlation_id, payload, event_id))

    async def report_kind_ended(
        self, correlation_id: str, kind_to_blueprint: KindToBlueprint, kind_index: int | None = None
    ) -> None:
        await self.flush()
        payload: dict[str, Any] = {"kindToBlueprint": kind_to_blueprint.to_dict()}
        if kind_index is not None:
            payload["kindIndex"] = kind_index
        event_id = f"{correlation_id}#{kind_to_blueprint.kind_identifier}#KIND#ENDED"
        await self._post([self._build_event("KIND", "ENDED", correlation_id, payload, event_id)])

    # ── BATCH ────────────────────────────────────────────────────────────────

    async def report_batch_started(
        self, correlation_id: str, batch_id: str, kind_identifier: str
    ) -> None:
        payload = {"batchId": batch_id, "kindIdentifier": kind_identifier}
        await self._enqueue(self._build_event("BATCH", "STARTED", correlation_id, payload, f"{batch_id}#BATCH#STARTED"))

    async def report_batch_ended(
        self, correlation_id: str, batch_id: str, kind_identifier: str, metrics: ExtractMetrics
    ) -> None:
        payload = {
            "batchId": batch_id,
            "kindIdentifier": kind_identifier,
            "metrics": metrics.to_dict(),
            "pendingUpsertIds": [],
        }
        await self._enqueue(self._build_event("BATCH", "ENDED", correlation_id, payload, f"{batch_id}#BATCH#ENDED"))
