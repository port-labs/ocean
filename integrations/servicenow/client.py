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
        self, resource_kind: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        offset = 0

        while True:
            params: dict[str, Any] = {
                "sysparm_offset": offset * PAGE_SIZE,
                "sysparm_limit": PAGE_SIZE,
                "sysparm_query": "ORDERBYsys_created_on",
            }
            try:
                response = await self.http_client.get(
                    url=f"{self.servicenow_url}/api/now/table/{resource_kind}",
                    params=params,
                )
                response.raise_for_status()
                records = response.json().get("result", [])

                if not records:
                    break

                total_rows = int(response.headers.get("X-Total-Count", 0))
                queried_rows = (offset * PAGE_SIZE) + len(records)

                logger.info(
                    f"Queried {queried_rows} from a total of {total_rows} {resource_kind}"
                )
                yield records

                if queried_rows >= total_rows:
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

    async def sanity_check(self) -> None:
        try:
            response = await self.http_client.get(
                f"{self.servicenow_url}/api/now/table/instance?sysparm_limit=1"
            )
            response.raise_for_status()
            logger.info("Servicenow sanity check passed")
            logger.info(
                f"Servicenow instance name: {response.json().get('result', [])[0].get('instance_name')}"
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
