from typing import Any, AsyncGenerator, Optional

import httpx
from httpx import ConnectTimeout, ReadTimeout, Response
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig
from azure_devops.client.auth import AuthProvider
from azure_devops.client.rate_limiter import (
    AzureDevOpsRateLimiter,
    LIMIT_RESET_HEADER,
    LIMIT_RETRY_AFTER_HEADER,
)

PAGE_SIZE = 50
CONTINUATION_TOKEN_HEADER = "x-ms-continuationtoken"
CONTINUATION_TOKEN_KEY = "continuationToken"
MAX_TIMEMOUT_RETRIES = 3
# ADO TSTU (Team Services Time Units) budget resets on a 5-minute rolling window.
# Both the retry backoff cap and the ReadTimeout cooldown are set to this value so
# the integration always waits out the full reset window before retrying.
ADO_RATE_LIMIT_WINDOW_SECONDS = 300


class HTTPBaseClient:
    def __init__(self, auth_provider: AuthProvider) -> None:
        self._client = OceanAsyncClient(
            retry_config=RetryConfig(
                retry_after_headers=[
                    LIMIT_RESET_HEADER,
                    LIMIT_RETRY_AFTER_HEADER,
                ],
                max_backoff_wait=ADO_RATE_LIMIT_WINDOW_SECONDS,
            ),
            timeout=ocean.config.client_timeout,
        )
        self._auth_provider = auth_provider
        self._rate_limiter = AzureDevOpsRateLimiter()

    async def send_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Response | None:
        auth_headers = await self._auth_provider.get_auth_headers()
        headers = {**(headers or {}), **auth_headers}
        self._client.follow_redirects = True

        try:
            async with self._rate_limiter:
                response = await self._client.request(
                    method=method,
                    url=url,
                    data=data,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response.status_code == 404:
                logger.warning(f"Couldn't access url: {url}. Failed due to 404 error")
                return None
            else:
                if response.status_code == 401:
                    logger.error(
                        f"Couldn't access url {url}. Make sure the {self._auth_provider.auth_description} is valid!"
                    )
                logger.error(
                    f"Request with bad status code {response.status_code}: {method} to url {url}. Response body: {e.response.text}"
                )
                raise e
        except httpx.HTTPError as e:
            if isinstance(e, (ReadTimeout, ConnectTimeout)):
                await self._rate_limiter.signal_throttle(ADO_RATE_LIMIT_WINDOW_SECONDS)
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
        top_param: Optional[str] = None,
        skip_param: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if not top_param:
            top_param = "$top"
        if not skip_param:
            skip_param = "$skip"
        default_params = {top_param: PAGE_SIZE, skip_param: 0}
        params = {**default_params, **(params or {})}
        timeout_retries = 0
        total_items_fetched = 0
        while True:
            if max_results and total_items_fetched >= max_results:
                break
            if max_results:
                params[top_param] = min(PAGE_SIZE, max_results - total_items_fetched)
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
                    params[skip_param] += len(objects_page)
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
