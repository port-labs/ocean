from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from integration import (
    CloudCostV1Selector,
    CloudCostV2Selector,
    KubecostV1Selector,
    KubecostV2Selector,
)

KUBECOST_API_VERSION_1 = "v1"


class KubeCostClient:
    def __init__(self, kubecost_host: str, kubecost_api_version: str):
        self.kubecost_host = kubecost_host
        self.kubecost_api_version = kubecost_api_version
        self.http_client = http_async_client

    def generate_params(
        self,
        selector: (
            CloudCostV1Selector
            | CloudCostV2Selector
            | KubecostV1Selector
            | KubecostV2Selector
        ),
    ) -> dict[str, str]:
        params = selector.dict(exclude_unset=True, by_alias=True)
        params.pop("query")
        return params

    async def get_kubesystem_cost_allocation(
        self, selector: KubecostV1Selector | KubecostV2Selector
    ) -> list[dict[str, Any]]:
        """Calls the Kubecost allocation endpoint to return data for cost and usage
        https://docs.kubecost.com/apis/apis-overview/api-allocation
        """

        params: dict[str, str] = {
            "window": selector.window,
            **self.generate_params(selector),
        }

        try:
            response = await self.http_client.get(
                url=f"{self.kubecost_host}/model/allocation",
                params=params,
            )
            response.raise_for_status()
            return response.json()["data"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching kubecost data: {e}")
            raise

    async def get_cloud_cost_allocation(
        self, selector: CloudCostV1Selector | CloudCostV2Selector
    ) -> list[dict[str, Any]]:
        """Calls the Kubecost cloud  allocation API. It uses the Aggregate endpoint which returns detailed cloud cost data
        https://docs.kubecost.com/apis/apis-overview/cloud-cost-api
        """
        url = f"{self.kubecost_host}/model/cloudCost"

        if self.kubecost_api_version == KUBECOST_API_VERSION_1:
            url = f"{self.kubecost_host}/model/cloudCost/aggregate"

        params: dict[str, str] = {
            "window": selector.window,
            **self.generate_params(selector),
        }

        try:
            response = await self.http_client.get(
                url=url,
                params=params,
            )
            response.raise_for_status()
            return response.json()["data"]["sets"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching kubecost data: {e}")
            raise

    def sanity_check(self) -> None:
        try:
            response = httpx.get(f"{self.kubecost_host}/model/installInfo", timeout=5)
            response.raise_for_status()
            logger.info("Kubecost sanity check passed")
            logger.info(f"Kubecost version: {response.json().get('version')}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kubecost failed connectivity check to the Kubecost instance because of HTTP error: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"Kubecost failed connectivity check to the Kubecost instance because of HTTP error: {e}"
            )
            raise
