"""
Report resync aborted via integ-service.

When the health checker runs in a sidecar and the main app is dead, calls the
integ-service abort endpoint so the resync is marked aborted and metrics are updated.
Uses sync HTTP so the health checker process can call it without asyncio.
"""

from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from loguru import logger

from port_ocean.health_checker.config import HealthCheckerSettings


def _get_port_client() -> httpx.Client:
    return httpx.Client(timeout=10.0)


def _get_access_token(
    client: httpx.Client, api_url: str, client_id: str, client_secret: str
) -> Optional[str]:
    try:
        response = client.post(
            f"{api_url}/auth/access_token",
            json={"clientId": client_id, "clientSecret": client_secret},
        )
        response.raise_for_status()
        data = response.json()
        return f"{data.get('tokenType', 'Bearer')} {data['accessToken']}"
    except Exception as e:
        logger.warning("Failed to get Port access token: {}", e)
        return None


def _get_integration(
    client: httpx.Client, api_url: str, integration_identifier: str, token: str
) -> Optional[dict[str, Any]]:
    try:
        response = client.get(
            f"{api_url}/integration/{quote_plus(integration_identifier)}",
            headers={"Authorization": token},
        )
        response.raise_for_status()
        return response.json().get("integration")
    except Exception as e:
        logger.warning("Failed to get integration from Port: {}", e)
        return None


def _get_latest_resync_id(
    client: httpx.Client,
    api_url: str,
    integration_internal_id: str,
    token: str,
) -> Optional[str]:
    try:
        response = client.get(
            f"{api_url}/integration/{quote_plus(integration_internal_id)}/syncsMetadata",
            headers={"Authorization": token},
        )
        response.raise_for_status()
        data = response.json().get("data")
        if data and len(data) > 0:
            return data[0].get("eventId")
        return None
    except Exception as e:
        logger.warning("Failed to get latest resync id from ingest: {}", e)
        return None


def report_resync_aborted_to_port(config: HealthCheckerSettings) -> None:
    """
    Call integ-service to abort the current resync.

    POST /metrics/integration/:integrationIdentifier/resync/:resyncId/abort with Authorization header.
    Fetches latest resyncId from /syncsMetadata first.
    """
    if (
        not config.port_base_url
        or not config.port_client_id
        or not config.port_client_secret
        or not config.integration_identifier
    ):
        return

    base_url = config.port_base_url.rstrip("/")
    api_url = f"{base_url}/v1"

    client = _get_port_client()
    try:
        token = _get_access_token(
            client, api_url, config.port_client_id, config.port_client_secret
        )
        if not token:
            return

        integration = _get_integration(
            client, api_url, config.integration_identifier, token
        )
        if not integration:
            return

        resync_id = _get_latest_resync_id(client, api_url, integration["_id"], token)
        if not resync_id:
            return

        logger.info("Latest resyncId: {}", resync_id)

        url = (
            f"{api_url}/integration/"
            f"{quote_plus(config.integration_identifier)}/resync/{resync_id}/abort"
        )
        try:
            response = client.post(
                url,
                headers={"Authorization": token},
            )
            if response.is_success:
                logger.info(
                    "Reported resync aborted to integ-service (integrationIdentifier={})",
                    config.integration_identifier,
                )
            else:
                logger.warning(
                    "integ-service resync abort returned {}: {}",
                    response.status_code,
                    response.text,
                )
        except Exception as e:
            logger.warning("Failed to POST resync abort to integ-service: {}", e)
    finally:
        client.close()
