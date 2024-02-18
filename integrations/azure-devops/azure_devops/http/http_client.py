import httpx
from httpx import Timeout, BasicAuth, Response
from typing import Any, AsyncGenerator, Optional
from port_ocean.utils import http_async_client
from loguru import logger

PAGE_SIZE = 50
REQUEST_TIMEOUT_SECONDS = 30
CONTINUATION_TOKEN_HEADER = "x-ms-continuationtoken"
ALLOW_REDIRECTS = True


class HTTPBaseClient:
    def __init__(self, personal_access_token: str) -> None:
        self._async_client = http_async_client
        # Username isn't required in basic auth to Azure Devops
        self._auth = BasicAuth("", personal_access_token)
        self._timeout = Timeout(REQUEST_TIMEOUT_SECONDS)
        self._follow_redirects = ALLOW_REDIRECTS

    @staticmethod
    def _parse_response_values(response: Response) -> list[dict[Any, Any]]:
        return response.json()["value"]

    def send_sync_get_request(
        self, url: str, params: Optional[dict[str, Any]] = None
    ) -> Response:
        try:
            response = httpx.get(
                url,
                params=params,
                auth=self._auth,
                timeout=self._timeout,
                follow_redirects=self._follow_redirects,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response.status_code == 401:
                logger.error(
                    f"Couldn't access url {url} . Make sure the PAT (Personal Access Token) is valid!"
                )
            else:
                logger.error(
                    f"Request with bad status code {response.status_code}: GET to url {url}: {str(e)}"
                )
                raise e
        except Exception as e:
            logger.error(f"Couldn't send get request to url {url}: {str(e)}")
            raise e
        return response

    async def send_get_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Response:
        return await self._send_request(
            method="get", url=url, params=params, headers=headers
        )

    async def send_post_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[str | dict[Any, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Response:
        return await self._send_request(
            method="post", params=params, url=url, data=data, headers=headers
        )

    async def _send_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Response:
        try:
            response = await self._async_client.request(
                method=method,
                url=url,
                data=data,
                params=params,
                auth=self._auth,
                follow_redirects=self._follow_redirects,
                timeout=self._timeout,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response.status_code == 401:
                logger.error(
                    f"Couldn't access url {url} . Make sure the PAT (Personal Access Token) is valid!"
                )
            else:
                logger.error(
                    f"Request with bad status code {response.status_code}: {method} to url {url}: {str(e)}"
                )
                raise e
        except Exception as e:
            logger.error(f"Couldn't send request {method} to url {url}: {str(e)}")
            raise e
        logger.debug(
            f"{method} Request to {url} got {response.status_code} -> {str(response.content)}"
        )
        return response

    async def _get_paginated_by_top_and_continuation_token(
        self, url: str, additional_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        continuation_token = ""
        while True:
            params: dict[str, Any] = {
                "$top": PAGE_SIZE,
                "continuationToken": continuation_token,
            }
            if additional_params:
                params.update(additional_params)
            response = await self.send_get_request(url, params=params)
            logger.debug(
                f"Found {len(response.json()['value'])} objects in url {url} with params: {params}"
            )
            yield self._parse_response_values(response)
            if CONTINUATION_TOKEN_HEADER not in response.headers:
                break
            continuation_token = response.headers.get(CONTINUATION_TOKEN_HEADER)

    async def _get_paginated_by_top_and_skip(
        self, url: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        default_params = {"$top": PAGE_SIZE, "$skip": 0}
        if params:
            params.update(**default_params)
        else:
            params = default_params
        while True:
            objects_page = self._parse_response_values(
                await self.send_get_request(url, params=params)
            )
            if objects_page:
                logger.debug(
                    f"Found {len(objects_page)} objects in url {url} with params: {params}"
                )
                yield objects_page
                params["$skip"] += PAGE_SIZE
            else:
                break
