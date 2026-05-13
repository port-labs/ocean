from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication


def _truncate(text: str, max_len: int = 256) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


class LifecycleClient:
    """Best-effort HTTP client for the integration-life-cycle service.

    Sends resync lifecycle events (started / finished / failed / aborted) to
    the external transform service.  Every public method swallows all exceptions
    so that lifecycle reporting never disrupts the core resync flow.
    """

    _client: httpx.AsyncClient

    def __init__(self, base_url: str, auth: PortAuthentication) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10))

    def _build_body(self, status: str, **extra: Any) -> dict[str, Any]:
        return {"status": status, **extra}

    async def _notify(
        self, resync_id: str, integration_id: str, body: dict[str, Any]
    ) -> None:
        """POST /v1/lifecycle/{resync_id}/{integration_id} -- best-effort, never raises."""
        url = f"{self.base_url}/v1/lifecycle/{resync_id}/{integration_id}"
        status = body.get("status", "unknown")
        try:
            headers = await self.auth.headers()
            response = await self._client.post(url, headers=headers, json=body)
            if response.is_error:
                escaped_response_text = response.text.replace("{", "{{").replace(
                    "}", "}}"
                )
                logger.warning(
                    f"Lifecycle API returned an error for status={status} {escaped_response_text}",
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

    async def notify_started(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
        started_at: datetime | None = None,
    ) -> None:
        started_at = started_at or datetime.now(tz=timezone.utc)
        body = self._build_body(
            "started",
            integration_type=integration_type,
            started_at=started_at.isoformat(),
        )
        logger.info(
            f"Notifying lifecycle API for status=started, resync_id={resync_id}, integration_id={integration_id}"
        )
        await self._notify(resync_id, integration_id, body)

    async def notify_finished(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
    ) -> None:
        body = self._build_body("finished", integration_type=integration_type)
        logger.info(
            f"Notifying lifecycle API for status=finished, resync_id={resync_id}, integration_id={integration_id}"
        )
        await self._notify(resync_id, integration_id, body)

    async def notify_failed(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
    ) -> None:
        body = self._build_body("failed", integration_type=integration_type)
        logger.info(
            f"Notifying lifecycle API for status=failed, resync_id={resync_id}, integration_id={integration_id}"
        )
        await self._notify(resync_id, integration_id, body)

    async def notify_aborted(
        self,
        resync_id: str,
        integration_id: str,
        integration_type: str,
    ) -> None:
        body = self._build_body("aborted", integration_type=integration_type)
        logger.info(
            f"Notifying lifecycle API for status=aborted, resync_id={resync_id}, integration_id={integration_id}"
        )
        await self._notify(resync_id, integration_id, body)
