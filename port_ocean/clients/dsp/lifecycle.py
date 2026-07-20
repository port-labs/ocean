from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.dsp.lifecycle_http import get_lifecycle_http_client
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.version import __integration_version__, __version__


class LifecycleAttributes(TypedDict):
    ingestUrl: str


class GranularityType(Enum):
    KIND = "KIND"
    BATCH = "BATCH"
    LIVE_EVENT = "LIVE_EVENT"
    RECONCILIATION = "RECONCILIATION"


class LifecycleClient:
    """Client for the integration-life-cycle service."""

    def __init__(self, auth: PortAuthentication) -> None:
        self._lifecycle_http_client = get_lifecycle_http_client(auth)
        self._lifecycle_attributes: LifecycleAttributes | None = None
        self._lifecycle_auth = auth

    async def _get_current_integration(self) -> dict[str, Any]:
        logger.info(
            f"Fetching integration with id: {self._lifecycle_auth.integration_identifier}"
        )
        response = await self._lifecycle_auth.client.get(
            f"{self._lifecycle_auth.api_url}/integration/{self._lifecycle_auth.integration_identifier}",
            headers=await self._lifecycle_auth.headers(),
            params={
                "oceanCoreVersion": __version__,
                "isPolling": "false",
            },
        )
        handle_port_status_code(response)
        return response.json().get("integration", {})

    async def get_lifecycle_attributes(self) -> LifecycleAttributes:
        if self._lifecycle_attributes is None:
            response = await self._get_current_integration()
            self._lifecycle_attributes = response["lifecycleAttributes"]
        return self._lifecycle_attributes

    async def _lifecycle_base_url(self) -> str:
        attributes = await self.get_lifecycle_attributes()
        return attributes["ingestUrl"].rstrip("/")

    def _build_body(self, status: str, **extra: Any) -> dict[str, Any]:
        return {"status": status, **extra}

    async def _resync_url(self, event_id: str) -> str:
        return f"{await self._lifecycle_base_url()}/{event_id}"

    async def _granular_url(self, event_id: str, granularity: GranularityType) -> str:
        return (
            f"{await self._lifecycle_base_url()}/{event_id}"
            f"/{granularity.value.lower()}"
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
        logger.info(f"Notifying lifecycle API resync started, resync_id={resync_id}")
        await self._lifecycle_http_client.do_post(
            await self._resync_url(resync_id), json=body
        )

    async def notify_resync_finished(
        self, resync_id: str, integration_id: str, integration_type: str
    ) -> None:
        body = self._build_body(
            "finished",
            integration_id=integration_id,
            integration_type=integration_type,
            integration_version=__integration_version__,
            ocean_version=__version__,
        )
        logger.info(f"Notifying lifecycle API resync finished, resync_id={resync_id}")
        await self._lifecycle_http_client.do_post(
            await self._resync_url(resync_id), json=body
        )

    async def notify_resync_failed(
        self, resync_id: str, integration_id: str, integration_type: str
    ) -> None:
        body = self._build_body("failed")
        logger.info(f"Notifying lifecycle API resync failed, resync_id={resync_id}")
        await self._lifecycle_http_client.do_post(
            await self._resync_url(resync_id), json=body
        )

    async def notify_resync_aborted(
        self, resync_id: str, integration_id: str, integration_type: str
    ) -> None:
        body = self._build_body("aborted")
        logger.info(f"Notifying lifecycle API resync aborted, resync_id={resync_id}")
        await self._lifecycle_http_client.do_post(
            await self._resync_url(resync_id), json=body
        )

    async def get_resync_status(self, resync_id: str) -> str | None:
        logger.debug(f"Polling lifecycle API resync status, resync_id={resync_id}")
        response = await self._lifecycle_http_client.do_get(
            await self._resync_url(resync_id)
        )
        if response is None:
            return None
        status = response.get("status")
        if not isinstance(status, str):
            return None
        return status.lower()

    # ── Granular (3-segment URL) ──────────────────────────────────────────────

    def _build_granular_body(
        self, status: str, kind_identifier: str | None, **extra: Any
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
            f"Notifying lifecycle API for status=started granularity={granularity.value}"
        )
        await self._lifecycle_http_client.do_post(
            await self._granular_url(event_id, granularity), json=body
        )

    async def notify_finished(
        self,
        event_id: str,
        integration_type: str,
        granularity: GranularityType,
        kind_identifier: str | None = None,
    ) -> None:
        body = self._build_granular_body(
            "finished", kind_identifier, integration_type=integration_type
        )
        logger.info(
            f"Notifying lifecycle API for status=finished granularity={granularity.value}"
        )
        await self._lifecycle_http_client.do_post(
            await self._granular_url(event_id, granularity), json=body
        )

    async def notify_failed(
        self,
        event_id: str,
        granularity: GranularityType,
        kind_identifier: str | None = None,
    ) -> None:
        body = self._build_granular_body("failed", kind_identifier)
        logger.info(
            f"Notifying lifecycle API for status=failed granularity={granularity.value}"
        )
        await self._lifecycle_http_client.do_post(
            await self._granular_url(event_id, granularity), json=body
        )

    async def notify_aborted(
        self,
        event_id: str,
        granularity: GranularityType,
        kind_identifier: str | None = None,
    ) -> None:
        body = self._build_granular_body("aborted", kind_identifier)
        logger.info(
            f"Notifying lifecycle API for status=aborted granularity={granularity.value}"
        )
        await self._lifecycle_http_client.do_post(
            await self._granular_url(event_id, granularity), json=body
        )
