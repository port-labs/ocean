from datetime import datetime, timezone
from typing import Any
from enum import Enum

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.version import __integration_version__, __version__


def _truncate(text: str, max_len: int = 256) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


class GranularityType(Enum):
    RESYNC = "RESYNC"
    KIND = "KIND"
    BATCH = "BATCH"
    LIVE_EVENT = "LIVE_EVENT"
    RECONCILIATION = "RECONCILIATION"


class LifecycleClient:
    """Best-effort HTTP client for the integration-life-cycle service.

    Sends resync lifecycle events (started / finished / failed / aborted) to
    the external transform service.  Every public method swallows all exceptions
    so that lifecycle reporting never disrupts the core resync flow.

    Two tiers of endpoints:
      - Resync-level  POST /v1/lifecycle/{event_id}
        Called once at the very start and once at the very end of a resync.
        integration_id is carried in the JSON body (required only for "started").
      - Tier-level granular  POST /v1/lifecycle/{event_id}/{kind|batch|live_event|reconciliation}
        Called once per granularity per resync. For LIVE_EVENT, {event_id} is the
        live_event_id; for other granularities it is the resync_id.
    """

    _client: httpx.AsyncClient

    def __init__(self, base_url: str, auth: PortAuthentication) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10))

    def _build_body(self, status: str, **extra: Any) -> dict[str, Any]:
        return {"status": status, **extra}

    def _resync_url(self, event_id: str) -> str:
        return f"{self.base_url}/v1/lifecycle/{event_id}"

    def _granular_url(self, event_id: str, granularity: GranularityType) -> str:
        return f"{self.base_url}/v1/lifecycle/{event_id}/{granularity.value.lower()}"

    async def _post(self, url: str, body: dict[str, Any]) -> None:
        """POST lifecycle event -- best-effort, never raises."""
        status = body.get("status", "unknown")
        try:
            headers = await self.auth.headers()
            response = await self._client.post(url, headers=headers, json=body)
            if response.is_error:
                escaped = response.text.replace("{", "{{").replace("}", "}}")
                logger.warning(
                    f"Lifecycle API returned an error for status={status} {_truncate(escaped)}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
            else:
                logger.info(
                    f"Lifecycle API notified successfully for status={status}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
        except Exception as exc:
            logger.warning(
                f"Failed to notify lifecycle API for status={status}: {type(exc).__name__}: {exc}"
            )

    # ── Resync-level (2-segment URL) ─────────────────────────────────────────

    async def notify_resync_started(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
        started_at: datetime | None = None,
    ) -> None:
        started_at = started_at or datetime.now(tz=timezone.utc)
        body = self._build_body(
            "started",
            integration_id=integration_id,
            integration_type=integration_type,
            integration_version=__integration_version__,
            ocean_version=__version__,
            started_at=started_at.isoformat(),
        )
        logger.info(
            f"Notifying lifecycle API resync started, resync_id={resync_id}, integration_id={integration_id}"
        )
        await self._post(self._resync_url(resync_id), body)

    async def notify_resync_finished(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
    ) -> None:
        body = self._build_body("finished", integration_type=integration_type)
        logger.info(f"Notifying lifecycle API resync finished, resync_id={resync_id}")
        await self._post(self._resync_url(resync_id), body)

    async def notify_resync_failed(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
    ) -> None:
        body = self._build_body("failed")
        logger.info(f"Notifying lifecycle API resync failed, resync_id={resync_id}")
        await self._post(self._resync_url(resync_id), body)

    async def notify_resync_aborted(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
    ) -> None:
        body = self._build_body("aborted")
        logger.info(f"Notifying lifecycle API resync aborted, resync_id={resync_id}")
        await self._post(self._resync_url(resync_id), body)

    # ── Granular (3-segment URL) ──────────────────────────────────────────────

    def _build_granular_body(
        self,
        status: str,
        kind_identifier: str | None,
        **extra: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "status": status,
            "integration_version": __integration_version__,
            "ocean_version": __version__,
            **extra,
        }
        if kind_identifier is not None:
            body["kind_identifier"] = kind_identifier
        return body

    async def notify_started(
        self,
        event_id: str,
        integration_id: str,
        integration_type: str,
        granularity: GranularityType,
        started_at: datetime | None = None,
        kind_identifier: str | None = None,
    ) -> None:
        started_at = started_at or datetime.now(tz=timezone.utc)
        body = self._build_granular_body(
            "started",
            kind_identifier,
            integration_id=integration_id,
            integration_type=integration_type,
            started_at=started_at.isoformat(),
        )
        logger.info(
            f"Notifying lifecycle API for status=started granularity={granularity.value}, event_id={event_id}"
        )
        await self._post(self._granular_url(event_id, granularity), body)

    async def notify_finished(
        self,
        event_id: str,
        integration_type: str,
        granularity: GranularityType,
        kind_identifier: str | None = None,
    ) -> None:
        body = self._build_granular_body(
            "finished",
            kind_identifier,
            integration_type=integration_type,
        )
        logger.info(
            f"Notifying lifecycle API for status=finished granularity={granularity.value}, event_id={event_id}"
        )
        await self._post(self._granular_url(event_id, granularity), body)

    async def notify_failed(
        self,
        event_id: str,
        granularity: GranularityType,
        kind_identifier: str | None = None,
    ) -> None:
        body = self._build_granular_body("failed", kind_identifier)
        logger.info(
            f"Notifying lifecycle API for status=failed granularity={granularity.value}, event_id={event_id}"
        )
        await self._post(self._granular_url(event_id, granularity), body)

    async def notify_aborted(
        self,
        event_id: str,
        granularity: GranularityType,
        kind_identifier: str | None = None,
    ) -> None:
        body = self._build_granular_body("aborted", kind_identifier)
        logger.info(
            f"Notifying lifecycle API for status=aborted granularity={granularity.value}, event_id={event_id}"
        )
        await self._post(self._granular_url(event_id, granularity), body)
