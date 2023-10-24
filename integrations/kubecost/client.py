import typing
from typing import Any

import httpx
from loguru import logger

from integration import KubecostResourceConfig
from port_ocean.context.event import event


class KubeCostClient:
    def __init__(self, app_host: str):
        self.app_host = app_host
        self.http_client = httpx.AsyncClient()

    async def get_kubesystem_cost_allocation(self) -> list[dict[str, Any]]:
        """Calls the Kubecost allocation endpoint to return data for cost and usage
        https://docs.kubecost.com/apis/apis-overview/api-allocation
        """
        selector = typing.cast(KubecostResourceConfig, event.resource_config).selector
        params: dict[str, Any] = {
            "window": selector.window,
        }
        if selector.aggregate:
            params["aggregate"] = selector.aggregate
        if selector.step:
            params["step"] = selector.step
        if selector.accumulate:
            params["accumulate"] = selector.accumulate
        if selector.idle:
            params["idle"] = selector.idle
        if selector.external:
            params["external"] = selector.external
        if selector.filterClusters:
            params["filterClusters"] = selector.filterClusters
        if selector.filterNodes:
            params["filterNodes"] = selector.filterNodes
        if selector.filterNamespaces:
            params["filterNamespaces"] = selector.filterNamespaces
        if selector.filterControllerKinds:
            params["filterControllerKinds"] = selector.filterControllerKinds
        if selector.filterControllers:
            params["filterControllers"] = selector.filterControllers
        if selector.filterPods:
            params["filterPods"] = selector.filterPods
        if selector.filterAnnotations:
            params["filterAnnotations"] = selector.filterAnnotations
        if selector.filterLabels:
            params["filterLabels"] = selector.filterLabels
        if selector.filterServices:
            params["filterServices"] = selector.filterServices
        if selector.shareIdle:
            params["shareIdle"] = selector.shareIdle
        if selector.splitIdle:
            params["splitIdle"] = selector.splitIdle
        if selector.idleByNode:
            params["idleByNode"] = selector.idleByNode
        if selector.shareNamespaces:
            params["shareNamespaces"] = selector.shareNamespaces
        if selector.shareLabels:
            params["shareLabels"] = selector.shareLabels
        if selector.shareCost:
            params["shareCost"] = selector.shareCost

        try:
            response = await self.http_client.get(
                url=f"{self.app_host}/model/allocation",
                params=params,
            )
            response.raise_for_status()
            return response.json()["data"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_cloud_cost_allocation(self) -> list[dict[str, Any]]:
        """Calls the Kubecost cloud  allocation API. It uses the Aggregate endpoint which returns detailed cloud cost data
        https://docs.kubecost.com/apis/apis-overview/cloud-cost-api
        """
        selector = typing.cast(KubecostResourceConfig, event.resource_config).selector
        params: dict[str, str] = {
            "window": selector.window,
        }
        if selector.aggregate:
            params["aggregate"] = selector.aggregate
        if selector.filterInvoiceEntityIDs:
            params["filterInvoiceEntityIDs"] = selector.filterInvoiceEntityIDs
        if selector.filterAccountIDs:
            params["filterAccountIDs"] = selector.filterAccountIDs
        if selector.filterProviders:
            params["filterProviders"] = selector.filterProviders
        if selector.filterServices:
            params["filterServices"] = selector.filterServices
        if selector.filterLabel:
            params["filterLabel"] = selector.filterLabel

        try:
            response = await self.http_client.get(
                url=f"{self.app_host}/model/cloudCost/aggregate",
                params=params,
            )
            response.raise_for_status()
            return response.json()["data"]["sets"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
