from typing import Any, AsyncGenerator, Optional

import httpx
from httpx import BasicAuth, ReadTimeout, Response
from loguru import logger
from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig
from azure_devops.client.rate_limiter import (
    AzureDevOpsRateLimiter,
    LIMIT_RESET_HEADER,
    LIMIT_RETRY_AFTER_HEADER,
)

PAGE_SIZE = 50
CONTINUATION_TOKEN_HEADER = "x-ms-continuationtoken"
CONTINUATION_TOKEN_KEY = "continuationToken"
MAX_TIMEMOUT_RETRIES = 3


class HTTPBaseClient(OAuthClient):
    def __init__(self, personal_access_token: Optional[str] = None) -> None:
        super().__init__()
        self._client = OceanAsyncClient(
            retry_config=RetryConfig(
                retry_after_headers=[
                    LIMIT_RESET_HEADER,
                    LIMIT_RETRY_AFTER_HEADER,
                ],
            ),
        )
        self._personal_access_token = personal_access_token or ""
        self._rate_limiter = AzureDevOpsRateLimiter()

    def is_oauth_enabled(self) -> bool:
        """
        Safely determine whether OAuth is enabled for the current integration.

        Falls back to False when Ocean app/config are not initialized
        to preserve existing behavior in non-OAuth environments.
        """
        app = getattr(ocean, "app", None)
        config = getattr(app, "config", None) if app is not None else None
        return bool(getattr(config, "oauth_access_token_file_path", None))

    def _ensure_oauth_headers(
        self, headers: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Ensure the Authorization header is set correctly when OAuth is enabled.
        Falls back to PAT if OAuth token is not available (e.g., at app startup).
        """
        headers = headers or {}
        if self.is_oauth_enabled():
            try:
                access_token = self.external_access_token
                headers["Authorization"] = f"Bearer {access_token}"
            except ValueError:
                pass
        return headers

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        """
        Refresh Authorization header on retries when OAuth is enabled.
        Falls back to PAT if OAuth token is not available (e.g., at app startup).
        """
        if not self.is_oauth_enabled():
            return request

        try:
            access_token = self.external_access_token
            request.headers["Authorization"] = f"Bearer {access_token}"
        except ValueError:
            pass
        return request

    async def send_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        timeout: int = 5,
    ) -> Response | None:
        if self.is_oauth_enabled():
            self._client.auth = None
            headers = self._ensure_oauth_headers(headers)
            if not headers.get("Authorization"):
                self._client.auth = BasicAuth("", self._personal_access_token)
        else:
            self._client.auth = BasicAuth("", self._personal_access_token)

        self._client.follow_redirects = True

        try:
            async with self._rate_limiter:
                response = await self._client.request(
                    method=method,
                    url=url,
                    data=data,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response.status_code == 404:
                logger.warning(f"Couldn't access url: {url}. Failed due to 404 error")
                return None
            else:
                if response.status_code == 401:
                    logger.error(
                        f"Couldn't access url {url} . Make sure the PAT (Personal Access Token) is valid!"
                    )
                logger.error(
                    f"Request with bad status code {response.status_code}: {method} to url {url}"
                )
                raise e
        except httpx.HTTPError as e:
            logger.error(f"Couldn't send request {method} to url {url}: {str(e)}")
            raise e
        finally:
            if "response" in locals() and response:
                await self._rate_limiter.update_from_headers(response.headers)
        return response

    async def _get_paginated_by_top_and_continuation_token(
        self,
        url: str,
        data_key: str = "value",
        additional_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        continuation_token = None
        timeout_retries = 0

        while True:
            params: dict[str, Any] = {
                "$top": PAGE_SIZE,
                **(additional_params or {}),
            }
            if (
                continuation_token
            ):  # Only add continuationToken if it's not None or empty
                params["continuationToken"] = continuation_token

            try:
                response = await self.send_request(
                    "GET",
                    url,
                    params=params,
                )
                if not response:
                    break
                response_json = response.json()
                items = response_json[data_key]

                logger.info(
                    f"Found {len(items)} objects in url {url} with params: {params}"
                )
                yield items
                timeout_retries = 0
                continuation_token = response.headers.get(
                    CONTINUATION_TOKEN_HEADER
                ) or response_json.get(CONTINUATION_TOKEN_KEY)
                if not continuation_token:
                    logger.info(
                        f"No continuation token found, pagination complete for {url}"
                    )
                    break
            except ReadTimeout as e:
                timeout_retries = timeout_retries + 1
                if timeout_retries < MAX_TIMEMOUT_RETRIES:
                    logger.warning(
                        f"Request to {url} with {params} timed out, retrying ..."
                    )
                else:
                    logger.error(
                        f"Request to {url} with {params} has timed out {MAX_TIMEMOUT_RETRIES} times."
                    )
                    raise e

    async def _get_paginated_by_top_and_skip(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        max_results: Optional[int] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        default_params = {"$top": PAGE_SIZE, "$skip": 0}
        params = {**default_params, **(params or {})}
        timeout_retries = 0
        total_items_fetched = 0
        while True:
            if max_results and total_items_fetched >= max_results:
                break
            if max_results:
                params["$top"] = min(PAGE_SIZE, max_results - total_items_fetched)

            try:
                response = await self.send_request("GET", url, params=params)
                if not response:
                    break

                objects_page = response.json()["value"]
                if objects_page:
                    logger.info(
                        f"Found {len(objects_page)} objects in url {url} with params: {params} and max_results: {max_results}"
                    )
                    yield objects_page
                    total_items_fetched += len(objects_page)
                    params["$skip"] += len(objects_page)
                    timeout_retries = 0
                else:
                    break
            except ReadTimeout as e:
                timeout_retries = timeout_retries + 1
                if timeout_retries < MAX_TIMEMOUT_RETRIES:
                    logger.warning(
                        f"Request to {url} with {params} timed out, retrying ..."
                    )
                else:
                    logger.error(
                        f"Request to {url} with {params} has timed out {MAX_TIMEMOUT_RETRIES} times."
                    )
                    raise e
