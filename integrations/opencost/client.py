import typing
from typing import Any

import httpx
from loguru import logger

from integrations.opencost.integration import OpencostResourceConfig
from port_ocean.context.event import event


class OpenCostClient:
    def __init__(self, app_host: str):
        self.app_host = app_host
        self.http_client = httpx.AsyncClient()

    async def get_cost_allocation(self) -> list[dict[str, list[Any]]]:
        """Calls the OpenCost allocation endpoint to return data for cost and usage
        https://www.opencost.io/docs/integrations/api
        """
        selector = typing.cast(OpencostResourceConfig, event.resource_config).selector
        params = {
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
