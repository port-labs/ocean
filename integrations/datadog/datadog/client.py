import http
import json
import re
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import httpx
from http import HTTPStatus
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig

MAX_PAGE_SIZE = 100

DATADOG_UNKNOWN_STATUS_CODE = 512


def _create_datadog_retry_config() -> RetryConfig:
    """Retry transient Datadog API failures, including undocumented 512 responses at deep pagination."""
    return RetryConfig(
        retry_after_headers=["X-RateLimit-Reset", "Retry-After"],
        additional_retry_status_codes=[
            HTTPStatus.INTERNAL_SERVER_ERROR,
            DATADOG_UNKNOWN_STATUS_CODE,
        ],
        ignore_retry_after_status_codes=[
            HTTPStatus.INTERNAL_SERVER_ERROR,
            DATADOG_UNKNOWN_STATUS_CODE,
        ],
    )


def embed_credentials_in_url(url: str, username: str, token: str) -> str:
    """Inserts username and token into a given URL for Datadog webhook basic-auth."""
    parsed_url = urlparse(url)
    netloc_with_credentials = f"{username}:{token}@{parsed_url.netloc}"
    modified_url = urlunparse(
        (
            parsed_url.scheme,
            netloc_with_credentials,
            parsed_url.path,
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment,
        )
    )
    return modified_url


class DatadogClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        app_key: str,
        access_token: Optional[str] = None,
    ):
        self.api_url = api_url
        self.dd_api_key = api_key
        self.dd_app_key = app_key
        self.access_token = access_token
        self.http_client = OceanAsyncClient(
            retry_config=_create_datadog_retry_config(),
            timeout=ocean.config.client_timeout,
        )

    @property
    def datadog_web_url(self) -> str:
        """Replaces 'api' with 'app' in Datadog URLs."""
        return re.sub(r"https://api\.", "https://app.", self.api_url)

    @property
    async def auth_headers(self) -> dict[str, Any]:
        if self.access_token:
            return {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        return {
            "DD-API-KEY": self.dd_api_key,
            "DD-APPLICATION-KEY": self.dd_app_key,
            "Content-Type": "application/json",
        }

    def _log_rate_limit_context(
        self, url: str, method: str, response: httpx.Response
    ) -> None:
        if response.status_code != http.HTTPStatus.TOO_MANY_REQUESTS:
            return

        logger.bind(
            remaining=response.headers.get("X-RateLimit-Remaining"),
            reset=response.headers.get("X-RateLimit-Reset"),
            method=method,
            url=url,
        ).warning(f"Datadog rate limit hit — {method} {url}")

    async def send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        logger.debug(f"Sending request {method} to endpoint {url}")

        response = await self.http_client.request(
            url=url,
            method=method,
            headers=await self.auth_headers,
            params=params,
            json=json_data,
        )
        self._log_rate_limit_context(url, method, response)
        response.raise_for_status()
        return response.json()

    async def create_webhooks_if_not_exists(
        self, base_url: Any, webhook_secret: Any
    ) -> None:
        webhook_name = "PORT"
        dd_webhook_url = f"{self.api_url}/api/v1/integration/webhooks/configuration/webhooks/{webhook_name}"

        try:
            if await self._webhook_exists(dd_webhook_url):
                logger.info("Webhook already exists")
                return

            logger.info("Subscribing to Datadog webhooks...")

            base_webhook_url = f"{base_url}/integration/webhook"
            modified_url = (
                embed_credentials_in_url(base_webhook_url, "port", webhook_secret)
                if webhook_secret
                else base_webhook_url
            )

            body = {
                "name": webhook_name,
                "url": modified_url,
                "encode_as": "json",
                "payload": json.dumps(
                    {
                        "id": "$ID",
                        "message": "$TEXT_ONLY_MSG",
                        "priority": "$PRIORITY",
                        "last_updated": "$LAST_UPDATED",
                        "event_type": "$EVENT_TYPE",
                        "event_url": "$LINK",
                        "service": "$HOSTNAME",
                        "service_id": "$SERVICE_ID",
                        "service_name": "$SERVICE_NAME",
                        "creator": "$USER",
                        "title": "$EVENT_TITLE",
                        "date": "$DATE",
                        "org_id": "$ORG_ID",
                        "org_name": "$ORG_NAME",
                        "alert_id": "$ALERT_ID",
                        "alert_metric": "$ALERT_METRIC",
                        "alert_status": "$ALERT_STATUS",
                        "alert_title": "$ALERT_TITLE",
                        "alert_type": "$ALERT_TYPE",
                        "tags": "$TAGS",
                        "body": "$EVENT_MSG",
                    }
                ),
            }

            result = await self.send_api_request(
                url=dd_webhook_url, method="POST", json_data=body
            )

            logger.info(f"Webhook Subscription Response: {result}")

        except Exception as e:
            logger.error(f"Failed to create a webhook: {str(e)}, skipping...")

    async def _webhook_exists(self, webhook_url: str) -> bool:
        try:
            webhook = await self.send_api_request(url=webhook_url)
            return bool(webhook)
        except httpx.HTTPStatusError as err:
            logger.warning(
                f"An error occurred while checking if a webhook exists. Error: {str(err)}. Skipping webhook setup."
            )
            return False
