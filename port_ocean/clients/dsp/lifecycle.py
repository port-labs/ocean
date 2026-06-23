import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig
from port_ocean.version import __integration_version__, __version__


class LifecycleAttributes(TypedDict):
    ingestUrl: str


def _truncate(text: str, max_len: int = 256) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


class OceanResyncHttpClient(OceanAsyncClient):
    """Best-effort authenticated HTTP client. Never raises; logs errors and swallows."""

    def __init__(self, auth: PortAuthentication, timeout: int = 10) -> None:
        self._lifecycle_auth = auth
        super().__init__(
            timeout=timeout,
            retry_config=RetryConfig(
                retryable_methods=[
                    "POST",
                    "HEAD",
                    "GET",
                    "PUT",
                    "DELETE",
                    "OPTIONS",
                    "TRACE",
                ]
            ),
        )

    async def _raw_post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await super().post(url, **kwargs)

    async def _do_post(self, url: str, json: dict[str, Any] | None = None) -> None:
        try:
            headers = await self._lifecycle_auth.headers()
            response = await self._raw_post(url, headers=headers, json=json)

            if response.is_error:
                escaped = response.text.replace("{", "{{").replace("}", "}}")
                logger.warning(
                    f"API returned an error for POST {url}: {_truncate(escaped)}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
            else:
                logger.info(
                    f"API request succeeded for POST {url}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Failed HTTP request: {type(exc).__name__}: {exc}")


class GranularityType(Enum):
    KIND = "KIND"
    BATCH = "BATCH"
    LIVE_EVENT = "LIVE_EVENT"
    RECONCILIATION = "RECONCILIATION"


class LifecycleClient(OceanResyncHttpClient):
    """Client for the integration-life-cycle service."""

    def __init__(self, auth: PortAuthentication) -> None:
        self._lifecycle_attributes: LifecycleAttributes | None = None
        super().__init__(auth=auth)

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
        await self._do_post(await self._resync_url(resync_id), json=body)

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
        await self._do_post(await self._resync_url(resync_id), json=body)

    async def notify_resync_failed(
        self, resync_id: str, integration_id: str, integration_type: str
    ) -> None:
        body = self._build_body("failed")
        logger.info(f"Notifying lifecycle API resync failed, resync_id={resync_id}")
        await self._do_post(await self._resync_url(resync_id), json=body)

    async def notify_resync_aborted(
        self, resync_id: str, integration_id: str, integration_type: str
    ) -> None:
        body = self._build_body("aborted")
        logger.info(f"Notifying lifecycle API resync aborted, resync_id={resync_id}")
        await self._do_post(await self._resync_url(resync_id), json=body)

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
        await self._do_post(await self._granular_url(event_id, granularity), json=body)

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
        await self._do_post(await self._granular_url(event_id, granularity), json=body)

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
        await self._do_post(await self._granular_url(event_id, granularity), json=body)

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
        await self._do_post(await self._granular_url(event_id, granularity), json=body)
