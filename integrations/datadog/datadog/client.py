import http
import re
from typing import Any, Optional

import httpx
from http import HTTPStatus
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import SKIP_RETRY_EXTENSION_KEY, RetryConfig

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
        org_name: Optional[str] = None,
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
        self.org_name = org_name

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

    async def validate_api_key(self) -> None:
        """Raise when Datadog rejects the API key (it ignores the application key).
        Docs: https://docs.datadoghq.com/api/latest/authentication/#validate-api-key
        """
        await self.send_api_request(f"{self.api_url}/api/v1/validate", skip_retry=True)

    async def get_current_user(self) -> dict[str, Any]:
        """Return the user that owns the credentials; needs no permission.
        Docs: https://docs.datadoghq.com/api/latest/users/#get-current-user
        """
        response = await self.send_api_request(
            f"{self.api_url}/api/v2/current_user", skip_retry=True
        )
        return response["data"]

    async def get_user_permissions(self, user_id: str) -> set[str]:
        """Return the names of the permissions *user_id* gets from their roles.
        Docs: https://docs.datadoghq.com/api/latest/users/#get-a-user-permissions
        """
        response = await self.send_api_request(
            f"{self.api_url}/api/v2/users/{user_id}/permissions", skip_retry=True
        )
        return {permission["attributes"]["name"] for permission in response["data"]}

    async def get_current_user_application_keys(self) -> list[dict[str, Any]]:
        """Return the application keys owned by the current user, with their scopes.
        Docs: https://docs.datadoghq.com/api/latest/key-management/#get-all-application-keys-owned-by-current-user
        """
        response = await self.send_api_request(
            f"{self.api_url}/api/v2/current_user/application_keys",
            params={"page[size]": 100},
            skip_retry=True,
        )
        return response["data"]

    async def send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        skip_retry: bool = False,
    ) -> Any:
        logger.debug(f"Sending request {method} to endpoint {url}")

        response = await self.http_client.request(
            url=url,
            method=method,
            headers=await self.auth_headers,
            params=params,
            json=json_data,
            extensions={SKIP_RETRY_EXTENSION_KEY: True} if skip_retry else None,
        )
        self._log_rate_limit_context(url, method, response)
        response.raise_for_status()
        return response.json()
