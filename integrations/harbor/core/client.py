import base64
from typing import Any, AsyncGenerator
from urllib.parse import quote_plus
import httpx

from loguru import logger

from port_ocean.utils.async_http import http_async_client
from port_ocean.utils.cache import cache_iterator_result

from ..utils.constants import DEFAULT_PAGE_SIZE, harbor_endpoints


class HarborClient:

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.auth_header = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        }

    async def _send_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = await http_async_client.request(
            method, url, headers=self.auth_header, **kwargs
        )
        response.raise_for_status()
        logger.debug(f"{method} {endpoint} - Status: {response.status_code}")
        return response

    async def _paginate(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = params or {}
        page = 1
        total_fetched = 0

        while True:
            params["page"] = page
            params["page_size"] = DEFAULT_PAGE_SIZE
            response = await self._send_request("GET", endpoint, params=params)
            batch = response.json()

            if not batch:
                break

            yield batch
            total_fetched += len(batch)

            total_count = int(response.headers.get("X-Total-Count", 0))
            logger.info(
                f"Fetched page {page} from {endpoint} "
                f"({total_fetched}/{total_count} items)"
            )

            if total_fetched >= total_count:
                break

            page += 1

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Fetching projects from Harbor")
        async for batch in self._paginate(harbor_endpoints.projects):
            yield batch

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Fetching users from Harbor")
        async for batch in self._paginate(harbor_endpoints.users):
            yield batch

    async def get_repositories(
        self, project_name: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Fetching repositories for project '{project_name}'")
        endpoint = harbor_endpoints.repositories.format(project_name=project_name)
        async for batch in self._paginate(endpoint):
            yield batch

    async def get_artifacts(
        self, project_name: str, repository_name: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Fetching artifacts for '{project_name}/{repository_name}'")
        endpoint = harbor_endpoints.artifacts.format(
            project_name=project_name,
            repository_name=quote_plus(repository_name),
        )
        params = {"with_scan_overview": "true", "with_tag": "true"}
        async for batch in self._paginate(endpoint, params=params):
            for artifact in batch:
                artifact["repository_name"] = f"{project_name}/{repository_name}"
            yield batch

    async def get_project_by_name(self, project_name: str) -> dict[str, Any]:
        logger.info(f"Fetching project '{project_name}'")
        endpoint = f"{harbor_endpoints.projects}/{project_name}"
        response = await self._send_request("GET", endpoint)
        return response.json()

    async def get_single_artifact(
        self, project_name: str, repository_name: str, artifact_digest: str
    ) -> dict[str, Any]:
        logger.info(
            f"Fetching artifact '{artifact_digest}' "
            f"from '{project_name}/{repository_name}'"
        )
        endpoint = (
            f"{harbor_endpoints.artifacts.format(project_name=project_name, repository_name=quote_plus(repository_name))}"
            f"/{artifact_digest}"
        )
        params = {"with_scan_overview": "true", "with_tag": "true"}
        response = await self._send_request("GET", endpoint, params=params)
        artifact = response.json()
        artifact["repository_name"] = f"{project_name}/{repository_name}"
        return artifact
