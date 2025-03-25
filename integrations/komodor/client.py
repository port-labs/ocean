from typing import Optional, Any, AsyncGenerator

from loguru import logger
from port_ocean.utils import http_async_client

from models import IssueBody, IssueScope

DEFAULT_PAGE_SIZE = 100


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

    async def get_clusters(self) -> AsyncGenerator[list[dict[str, Any]], Any]:
        res = await self._send_request(url=f"{self.api_url}/clusters")
        yield res.get("data", {}).get("clusters", [])

    async def get_all_services(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        current_page = 0
        service_default_page_size = 25
        while True:
            res = await self._send_request(url=f"{self.api_url}/services/search", data={
                "kind": [
                    "Deployment"
                ],
                "pagination": {
                    "pageSize": service_default_page_size,
                    "page": current_page
                }
            }, method="POST")
            yield res.get("data", {}).get("services", [])

            current_page = res.get("meta", {}).get("nextPage", None)
            if not current_page:
                logger.debug("No more service pages, breaking.")
                break

    async def get_risks(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        offset = 0
        default_risks_page_size = 50
        while True:
            res = await self._send_request(url=f"{self.api_url}/health/risks",
                                           params={"pageSize": default_risks_page_size, "offset": offset,
                                                   "checkCategory": ["workload",
                                                                     "infrastructure"],
                                                   "impactGroupType": ["dynamic"]})
            yield res.get("violations", [])

            if not res.get("hasMoreResults"):
                logger.debug("No more health risks pages, breaking.")
                break
            offset += default_risks_page_size

    async def get_issues(self) -> AsyncGenerator[list[dict[str, Any]], Any]:
        async for cluster in self.get_clusters():
            all_issues_in_cluster = []
            async for issue in self._get_issues_from_cluster(cluster):
                if issue:
                    for single_issue in issue:
                        all_issues_in_cluster.append(single_issue)
            yield all_issues_in_cluster

    async def _get_issues_from_cluster(self, clusters: list[dict[str, Any]]) -> AsyncGenerator[
        list[dict[str, Any]] | None, Any]:
        for cluster in clusters:
            cluster_name = cluster.get("name", None)
            if cluster_name is None:
                logger.error("Required cluster name parameter is missing")
                yield None

            body = IssueBody(scope=IssueScope(cluster=cluster_name)).dict()
            current_page = 0
            while True:
                body["pagination"] = {"pageSize": DEFAULT_PAGE_SIZE, "page": current_page}
                res = await self._send_request(url=f"{self.api_url}/clusters/issues/search", data=body,
                                               method="POST")
                issues = res.get("data", {}).get("issues", [])
                if issues is None:
                    yield None

                # enrich issue with cluster name
                for issue in issues:
                    issue["_clusterName"] = cluster_name
                yield issues
                current_page = res.get("meta", {}).get("nextPage", None)
                if not current_page:
                    logger.debug("No more issues pages, breaking.")
                    break
