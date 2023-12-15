import typing
from typing import Any, AsyncGenerator
import base64
import httpx
from loguru import logger

from integration import ServicenowResourceConfig
from port_ocean.context.event import event
from port_ocean.utils import http_async_client

PAGE_SIZE = 100


class ServicenowClient:
    def __init__(
        self, servicenow_host: str, servicenow_username: str, servicenow_password: str
    ):
        self.servicenow_host = servicenow_host
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
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        selector = typing.cast(ServicenowResourceConfig, event.resource_config).selector

        offset = 0

        while True:
            params: dict[str, Any] = {
                "sysparm_offset": offset * PAGE_SIZE,
                "sysparm_limit": PAGE_SIZE,
                "sysparm_query": "ORDERBYsys_created_on",
            }

            try:
                response = await self.http_client.get(
                    url=f"{self.servicenow_host}/api/now/table/{selector.path}",
                    params=params,
                )
                response.raise_for_status()
                records = response.json().get("result", [])

                if not records:
                    break

                yield records

                total_records = int(response.headers.get("X-Total-Count", 0))
                if (offset + 1) * PAGE_SIZE >= total_records:
                    break

                offset += 1

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching Servicenow data: {e}")
                raise
