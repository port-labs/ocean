from typing import Any, AsyncGenerator
import base64
import httpx
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 100


class ServicenowClient:
    def __init__(
        self, servicenow_url: str, servicenow_username: str, servicenow_password: str
    ):
        self.servicenow_url = servicenow_url
        self.servicenow_username = servicenow_username
        self.servicenow_password = servicenow_password
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_params["headers"])

    @property
    def api_auth_params(self) -> dict[str, Any]:
        auth_message = f"{self.servicenow_username}:{self.servicenow_password}"
        auth_bytes = auth_message.encode("ascii")
        b64_bytes = base64.standard_b64encode(auth_bytes)
        b64_message = b64_bytes.decode("ascii")

        return {
            "headers": {
                "Authorization": f"Basic {b64_message}",
                "Content-Type": "application/json",
            },
        }

    async def get_paginated_resource(
        self, resource_kind: str, api_query_params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:

        user_query = api_query_params.pop("sysparm_query", "")
        default_ordering = "ORDERBYDESCsys_created_on"
        enhanced_query = (
            f"{user_query}^{default_ordering}" if user_query else default_ordering
        )

        params: dict[str, Any] = {
            "sysparm_limit": PAGE_SIZE,
            "sysparm_query": enhanced_query,
            **api_query_params,
        }
        logger.info(
            f"Fetching Servicenow data for resource: {resource_kind} with request params: {params}"
        )
        url = f"{self.servicenow_url}/api/now/table/{resource_kind}"

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

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching Servicenow data: {e}")
                raise

    async def sanity_check(self) -> None:
        try:
            response = await self.http_client.get(
                f"{self.servicenow_url}/api/now/table/sys_user?sysparm_limit=1"
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
