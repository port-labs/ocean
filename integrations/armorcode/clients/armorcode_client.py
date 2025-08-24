import asyncio
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
            elif e.response.status_code == 429:
                logger.warning(
                    f"Armorcode Client API rate limit reached. Waiting for {e.response.headers.get('Retry-After', 60)} seconds."
                )
                await asyncio.sleep(int(e.response.headers.get("Retry-After", 60)))
            logger.error(f"API request failed for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during API request to {url}: {e}")
            raise

    async def get_products(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch products from the Armorcode API.
        Yields batches of products as lists of dicts.
        """
        endpoint = PRODUCTS_ENDPOINT
        params = {**self.DEFAULT_PARAMS, "pageNumber": 0}

        while True:
            try:
                response = await self._send_api_request(endpoint, params=params)
                products = response.get("content", [])

                if not isinstance(products, list):
                    break

                if not products:
                    logger.info(f"No products returned for page {params['pageNumber']}")
                    break

                logger.info(f"Fetched {len(products)} products from Armorcode API")
                yield products

                if response.get("last", True):
                    break

                params["pageNumber"] += 1
            except Exception as e:
                logger.error(f"Error fetching products: {e}")
                break

    async def get_all_subproducts(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch all subproducts from the Armorcode API.
        Yields batches of subproducts as lists of dicts.
        """
        endpoint = f"{SUB_PRODUCTS_ENDPOINT}"
        params = {**self.DEFAULT_PARAMS, "pageNumber": 0}

        while True:
            try:
                response = await self._send_api_request(endpoint, params=params)
                subproducts = response.get("content", [])
                if not isinstance(subproducts, list):
                    break

                if not subproducts:
                    logger.info(
                        f"No subproducts returned for page {params['pageNumber']}"
                    )
                    break

                logger.info(
                    f"Fetched {len(subproducts)} subproducts from Armorcode API"
                )
                yield subproducts

                if len(subproducts) < PAGE_SIZE:
                    break
                params["pageNumber"] += 1
            except Exception as e:
                logger.error(f"Error fetching subproducts: {e}")
                break

    async def get_all_findings(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch all findings from the Armorcode API using POST request.
        Yields batches of findings as lists of dicts.
        """
        endpoint = FINDINGS_ENDPOINT
        after_key = None
        payload = {
            "filters": {},
            "ignoreDuplicate": True,
            "ignoreMitigated": None,
            "sort": "",
            "ticketStatusRequired": True,
        }

        while True:
            try:
                params = {"size": PAGE_SIZE}
                if after_key is not None:
                    params["afterKey"] = after_key

                response = await self._send_api_request(
                    endpoint, method="POST", json_data=payload, params=params
                )
                findings = response["data"].get("findings", [])

                if not isinstance(findings, list):
                    break

                if not findings:
                    logger.info("No findings returned")
                    break

                logger.info(f"Fetched {len(findings)} findings from Armorcode API")
                yield findings

                after_key = response["data"].get("afterKey")
                if not after_key:
                    break

            except Exception as e:
                logger.error(f"Error fetching findings: {e}")
                break
