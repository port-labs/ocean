from typing import Any, AsyncGenerator, List, Dict, Optional
from httpx import HTTPStatusError, AsyncClient
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 100
PRODUCTS_ENDPOINT = "user/product/elastic/paged"
SUB_PRODUCTS_ENDPOINT = "user/sub-product/elastic"
FINDINGS_ENDPOINT = "api/findings"


class ArmorcodeClient:
    """
    Client for interacting with the Armorcode API using API key authentication.
    Implements methods to fetch products, subproducts, and findings
    """

    DEFAULT_PARAMS: dict[str, Any] = {
        "pageSize": PAGE_SIZE,
        "tags": "",
        "sortBy": "NAME",
        "direction": "ASC",
    }

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.http_client: AsyncClient = http_async_client

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an authenticated API request to the Armorcode API.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
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

    async def _get_paginated_resource(
        self,
        endpoint: str,
        method: str = "GET",
        content_key: str = "content",
        is_last_key: Optional[str] = "last",
        json_data: Optional[Dict[str, Any]] = None,
        use_offset_pagination: bool = True,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Centralized pagination method for all endpoints.

        Args:
            endpoint: API endpoint to paginate
            method: HTTP method (GET/POST)
            content_key: Key in response containing the data array
            is_last_key: Key indicating if it's the last page
            json_data: JSON payload for POST requests
            use_offset_pagination: True for pageNumber-based pagination, False for afterKey-based
        """
        page_number = 0
        after_key = None

        while True:
            try:
                params = {**self.DEFAULT_PARAMS}

                if use_offset_pagination:
                    params["pageNumber"] = page_number
                elif after_key is not None:
                    params["afterKey"] = after_key
                    # For afterKey pagination, we typically don't use pageNumber
                    if "pageNumber" in params:
                        del params["pageNumber"]

                response = await self._send_api_request(
                    endpoint, method=method, params=params, json_data=json_data
                )
                # Some endpoints (e.g., findings) return the payload nested under a "data" key
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

                # Determine if we should continue paginating
                if use_offset_pagination:
                    # When using offset pagination, rely on the provided last-page indicator key if present.
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

    async def get_products(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch products from the Armorcode API.
        Yields batches of products as lists of dicts.
        """
        async for products in self._get_paginated_resource(
            endpoint=PRODUCTS_ENDPOINT,
            method="GET",
            content_key="content",
            is_last_key="last",
        ):
            yield products

    async def get_all_subproducts(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch all subproducts from the Armorcode API.
        Yields batches of subproducts as lists of dicts.
        """
        async for subproducts in self._get_paginated_resource(
            endpoint=SUB_PRODUCTS_ENDPOINT,
            method="GET",
            content_key="content",
            is_last_key="last",
        ):
            yield subproducts

    async def get_all_findings(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch all findings from the Armorcode API using POST request.
        Yields batches of findings as lists of dicts.
        """
        async for findings in self._get_paginated_resource(
            endpoint=FINDINGS_ENDPOINT,
            method="POST",
            content_key="findings",
            is_last_key=None,  # Not used for afterKey pagination
            json_data={},  # Empty payload as in original
            use_offset_pagination=False,  # Use afterKey-based pagination
        ):
            yield findings
