from typing import Optional, Any, AsyncGenerator

from loguru import logger
from port_ocean.utils import http_async_client

from models import IssueRequestBody, IssueScope

# The page size may differ between entities base on their potential size
DEFAULT_PAGE_SIZE = 100
SERVICES_PAGE_SIZE = 25 # The service page size is smaller due to the potential extra data in labels and annotations
RISKS_PAGE_SIZE = 50 # The risks page size is smaller due to the potential extra data in the supportingData field


class KomodorClient:
    def __init__(self,
                 api_key: str,
                 api_url: Optional[str] = "https://api.komodor.com/api/v2"):
        self.api_key = api_key
        self.api_url = api_url
        self.http_client = http_async_client
        self.http_client.headers.update({"accept": "application/json",
                                         "X-API-KEY": api_key,
                                         "Content-Type": "application/json"})

    async def _send_request(self, url: str, params: Optional[dict[str, Any]] = None,
                            data: Optional[dict[str, Any]] = None, method: str = "GET") -> Any:
        res = await self.http_client.request(url=url, params=params, json=data, method=method)
        res.raise_for_status()
        return res.json()



    async def get_all_services(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        current_page = 0
        while True:
            response = await self._send_request(url=f"{self.api_url}/services/search", data={
                "kind": [
                    "Deployment",
                    "StatefulSet",
                    "DaemonSet",
                    "Rollout"
                ],
                "pagination": {
                    "pageSize": SERVICES_PAGE_SIZE,
                    "page": current_page
                }
            }, method="POST")
            yield response.get("data", {}).get("services", [])

            current_page = response.get("meta", {}).get("nextPage", None)
            if not current_page:
                logger.debug("No more service pages, breaking")
                break


    async def get_health_monitor(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        offset = 0
        while True:
            response = await self._send_request(url=f"{self.api_url}/health/risks",
                                           params={"pageSize": RISKS_PAGE_SIZE, "offset": offset,
                                                   "checkCategory": ["workload",
                                                                     "infrastructure"],
                                                   "impactGroupType": ["dynamic", "realtime"]})
            yield response.get("violations", [])

            if not response.get("hasMoreResults"):
                logger.debug("No more health risks pages, breaking")
                break
            offset += RISKS_PAGE_SIZE

    async def _get_clusters(self) -> AsyncGenerator[list[dict[str, Any]], Any]:
        res = await self._send_request(url=f"{self.api_url}/clusters")
        yield res.get("data", {}).get("clusters", [])


    async def _get_risks(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        offset = 0
        while True:
            response = await self._send_request(url=f"{self.api_url}/health/risks",
                                                params={"pageSize": RISKS_PAGE_SIZE, "offset": offset,
                                                        "checkCategory": ["workload",
                                                                          "infrastructure"],
                                                        "impactGroupType": ["dynamic"]})
            yield response.get("violations", [])

            if not response.get("hasMoreResults"):
                logger.debug("No more health risks pages, breaking")
                break
            offset += RISKS_PAGE_SIZE

    async def _get_issues(self) -> AsyncGenerator[list[dict[str, Any]], Any]:
        offset = 0
        while True:
            response = await self._send_request(url=f"{self.api_url}/health/risks",
                                                params={"pageSize:": RISKS_PAGE_SIZE, "offset": offset,
                                                        "checkType": ["unhealthyService"],
                                                        "impactGroupType": ["realtime"],
                                                        "checkCategory": ["workload"]})
            yield response.get("violations", [])
            if not response.get("hasMoreResults"):
                logger.debug("No more health issues pages, breaking")
                break
            offset += RISKS_PAGE_SIZE

    async def _get_issues_from_cluster(self, clusters: list[dict[str, Any]]) -> AsyncGenerator[
        list[dict[str, Any]] | None, Any]:
        for cluster in clusters:
            cluster_name = cluster.get("name", None)
            if cluster_name is None:
                logger.error("Required cluster name parameter is missing")
                yield None
                continue

            body = IssueRequestBody(scope=IssueScope(cluster=cluster_name)).dict()
            current_page = 0
            while True:
                body["pagination"] = {"pageSize": DEFAULT_PAGE_SIZE, "page": current_page}
                response = await self._send_request(url=f"{self.api_url}/clusters/issues/search", data=body,
                                               method="POST")
                issues = response.get("data", {}).get("issues", [])
                if issues is None:
                    yield None
                    continue

                # enrich issue with cluster name
                for issue in issues:
                    issue["_clusterName"] = cluster_name
                yield issues
                current_page = response.get("meta", {}).get("nextPage", None)
                if not current_page:
                    logger.debug("No more issues pages, breaking")
                    break
