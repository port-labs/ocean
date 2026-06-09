import http
import re
from typing import Any, Optional

import httpx
from http import HTTPStatus
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig

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


class DatadogClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        app_key: str,
        access_token: Optional[str] = None,
        org_id: Optional[str] = None,
    ):
        self.api_url = api_url
        self.dd_api_key = api_key
        self.dd_app_key = app_key
        self.access_token = access_token
        self.http_client = OceanAsyncClient(
            retry_config=_create_datadog_retry_config(),
            timeout=ocean.config.client_timeout,
        )
        self.org_id = org_id

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
