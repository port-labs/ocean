import typing
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils import http_async_client

from integration import CloudCostResourceConfig, OpencostResourceConfig


class OpenCostClient:
    def __init__(self, app_host: str):
        self.app_host = app_host
        self.http_client = http_async_client

    async def get_cost_allocation(self) -> list[dict[str, Any]]:
        """Calls the OpenCost allocation endpoint to return data for cost and usage
        https://www.opencost.io/docs/integrations/api
        """
        selector = typing.cast(OpencostResourceConfig, event.resource_config).selector
        params: dict[str, str] = {
            "window": selector.window,
        }
        if selector.aggregate:
            params["aggregate"] = selector.aggregate
        if selector.step:
            params["step"] = selector.step
        if selector.resolution:
            params["resolution"] = selector.resolution

        try:
            response = await self.http_client.get(
                url=f"{self.app_host}/allocation/compute",
                params=params,
            )
            response.raise_for_status()
            return response.json()["data"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_cloudcost(self) -> list[dict[str, dict[str, dict[str, Any]]]]:
        """
        Retrieves cloud cost data from cloud providers by reading cost
        and usage reports.
        Docs: https://www.opencost.io/docs/integrations/api#cloud-costs-api
        """
        selector = typing.cast(CloudCostResourceConfig, event.resource_config).selector
        params: dict[str, str] = {
            "window": selector.window,
        }
        if selector.aggregate:
            params["aggregate"] = selector.aggregate
        if selector.accumulate:
            params["accumulate"] = selector.accumulate
        if selector.filter:
            params["filter"] = selector.filter

        try:
            response = await self.http_client.get(
                url=f"{self.app_host}/cloudCost",
                params=params,
            )
            response.raise_for_status()
            return response.json()["data"]["sets"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
