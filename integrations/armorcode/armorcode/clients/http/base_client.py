from abc import ABC
from typing import Any, Dict, Optional, AsyncGenerator, List
from httpx import HTTPStatusError, AsyncClient
from loguru import logger
from port_ocean.utils import http_async_client

from ..auth.abstract_authenticator import AbstractArmorcodeAuthenticator


class BaseArmorcodeClient(ABC):
    """Base client for ArmorCode API interactions."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "pageSize": 100,
        "tags": "",
        "sortBy": "NAME",
        "direction": "ASC",
    }

    def __init__(self, base_url: str, authenticator: AbstractArmorcodeAuthenticator):
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator
        self.http_client: AsyncClient = http_async_client

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send an authenticated API request to the ArmorCode API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = self.authenticator.get_headers()
        auth_params = self.authenticator.get_auth_params()

        if params is None:
            params = {}
        params.update(auth_params)

        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Requested resource not found: {url}; message: {str(e)}"
                )
                return {}
            logger.error(f"API request failed for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during API request to {url}: {e}")
            raise

    async def send_paginated_request(
        self,
        endpoint: str,
        content_key: str = "content",
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        use_offset_pagination: bool = True,
        is_last_key: Optional[str] = "last",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send paginated API requests to the ArmorCode API."""
        page_number = 0
        after_key = None

        while True:
            try:
                params = {**self.DEFAULT_PARAMS}

                if use_offset_pagination:
                    params["pageNumber"] = page_number
                elif after_key is not None:
                    params["afterKey"] = after_key
                    if "pageNumber" in params:
                        del params["pageNumber"]

                response = await self.send_api_request(
                    endpoint, method=method, params=params, json_data=json_data
                )

                container: Dict[str, Any] = (
                    response.get("data", {})
                    if isinstance(response.get("data"), dict)
                    else response
                )
                items = container.get(content_key, [])

                if not isinstance(items, list):
                    break

                if not items:
                    logger.info(
                        f"No items returned for {endpoint} on page {page_number}"
                    )
                    break

                logger.info(f"Fetched {len(items)} items from {endpoint}")
                yield items

                if use_offset_pagination:
                    last_page = (
                        True
                        if is_last_key is None
                        else bool(container.get(is_last_key, True))
                    )
                    if last_page:
                        break
                    page_number += 1
                else:
                    after_key = container.get("afterKey")
                    if not after_key:
                        break

            except Exception as e:
                logger.error(f"Error paginating {endpoint}: {e}")
                break
