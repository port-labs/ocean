import httpx
from httpx import BasicAuth, Response
from typing import Any, AsyncGenerator, Optional
from port_ocean.utils import http_async_client
from loguru import logger

PAGE_SIZE = 50
CONTINUATION_TOKEN_HEADER = "x-ms-continuationtoken"


class HTTPBaseClient:
    def __init__(self, personal_access_token: str) -> None:
        self._client = http_async_client
        self._personal_access_token = personal_access_token

    async def send_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Response:
        self._client.auth = BasicAuth("", self._personal_access_token)
        self._client.follow_redirects = True

        try:
            response = await self._client.request(
                method=method,
                url=url,
                data=data,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response.status_code == 401:
                logger.error(
                    f"Couldn't access url {url} . Make sure the PAT (Personal Access Token) is valid!"
                )
            else:
                logger.exception(
                    f"Request with bad status code {response.status_code}: {method} to url {url}"
                )
            raise e
        except httpx.HTTPError as e:
            logger.error(f"Couldn't send request {method} to url {url}: {str(e)}")
            raise e
        return response

    async def _get_paginated_by_top_and_continuation_token(
        self, url: str, additional_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        continuation_token = None
        while True:
            params: dict[str, Any] = {
                "$top": PAGE_SIZE,
                **(additional_params or {}),
            }
            if (
                continuation_token
            ):  # Only add continuationToken if it's not None or empty
                params["continuationToken"] = continuation_token

            response = await self.send_request("GET", url, params=params)
            logger.info(
                f"Found {len(response.json()['value'])} objects in url {url} with params: {params}"
            )
            yield response.json()["value"]
            if CONTINUATION_TOKEN_HEADER not in response.headers:
                break
            continuation_token = response.headers.get(CONTINUATION_TOKEN_HEADER)

    async def _get_paginated_by_top_and_skip(
        self, url: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        default_params = {"$top": PAGE_SIZE, "$skip": 0}
        params = {**default_params, **(params or {})}
        while True:
            objects_page = (await self.send_request("GET", url, params=params)).json()[
                "value"
            ]
            if objects_page:
                logger.info(
                    f"Found {len(objects_page)} objects in url {url} with params: {params}"
                )
                yield objects_page
                params["$skip"] += PAGE_SIZE
            else:
                break
