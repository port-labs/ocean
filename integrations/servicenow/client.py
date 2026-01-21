from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from auth.abstract_authenticator import AbstractServiceNowAuthenticator

PAGE_SIZE = 100


class ServicenowClient:
    def __init__(
        self,
        servicenow_url: str,
        authenticator: AbstractServiceNowAuthenticator,
    ):
        self.servicenow_url = servicenow_url
        self.table_base_url = f"{self.servicenow_url}/api/now/table"
        self.authenticator = authenticator
        self.http_client = http_async_client

    async def _ensure_auth_headers(self) -> None:
        """Update HTTP client headers with current authentication."""
        headers = await self.authenticator.get_headers()
        self.http_client.headers.update(headers)

    async def get_paginated_resource(
        self, resource_kind: str, api_query_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        await self._ensure_auth_headers()

        safe_params = (api_query_params or {}).copy()
        user_query = safe_params.pop("sysparm_query", "")
        default_ordering = "ORDERBYDESCsys_created_on"
        enhanced_query = (
            f"{user_query}^{default_ordering}" if user_query else default_ordering
        )

        params: Optional[dict[str, Any]] = {
            "sysparm_limit": PAGE_SIZE,
            "sysparm_query": enhanced_query,
            **safe_params,
        }
        logger.info(
            f"Fetching Servicenow data for resource: {resource_kind} with request params: {params}"
        )
        url = f"{self.table_base_url}/{resource_kind}"

        while url:
            try:
                response = await self.http_client.get(
                    url=url,
                    params=params,
                )
                response.raise_for_status()
                records = response.json().get("result", [])

                yield records

                url = self.extract_next_link(response.headers.get("Link", ""))
                params = None

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP error occurred while fetching Servicenow data: {e}")
                raise

    async def sanity_check(self) -> None:
        await self._ensure_auth_headers()
        try:
            response = await self.http_client.get(
                f"{self.table_base_url}/sys_user?sysparm_limit=1"
            )
            response.raise_for_status()
            logger.info("Servicenow sanity check passed")
            logger.info(
                f"Retrieved sample Servicenow user with first name: {response.json().get('result', [])[0].get('first_name')}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Integration failed to connect to Servicenow instance as part of sanity check due to HTTP error: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError:
            logger.exception(
                "Integration failed to connect to Servicenow instance as part of sanity check due to HTTP error"
            )
            raise

    def extract_next_link(self, link_header: str) -> str:
        """
        Extracts the 'next' link from the Link header.
        """
        links = [link.strip() for link in link_header.split(",")]
        for link in links:
            if 'rel="next"' in link:
                return link.split(";")[0].strip("<>")
        return ""
