import base64
from typing import Any, AsyncGenerator, Dict, List
from port_ocean.utils import http_async_client
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean

BITBUCKET_EVENTS = [
    "repo:push",
    "pullrequest:created",
    "pullrequest:updated",
    "pullrequest:fulfilled",
    "pullrequest:rejected",
]

class BitbucketOceanIntegration:
    def __init__(self, username: str, app_password: str):
        self.http_client = http_async_client
        self.username = username
        self.app_password = app_password
        self.base_url = ocean.integration_config["bitbucket_base_url"]

    @property
    def auth_header(self) -> Dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def _fetch_paginated_data(self, endpoint: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        url = f"{self.base_url}/{endpoint}"
        
        while url:
            response = await self.http_client.get(url, headers=self.auth_header)
            response.raise_for_status()
            data = response.json()
            yield data.get("values", [])
            url = data.get("next")

    @cache_iterator_result()
    async def fetch_workspaces(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        async for data in self._fetch_paginated_data("workspaces"):
            yield data

    @cache_iterator_result()
    async def fetch_repositories(self, workspace: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        async for data in self._fetch_paginated_data(f"repositories/{workspace}"):
            yield data

    async def fetch_projects(self, workspace: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.debug(f"Fetching projects for workspace: {workspace}")
        async for data in self._fetch_paginated_data(f"workspaces/{workspace}/projects"):
            yield data

    async def fetch_pull_requests(self, workspace: str, repo_slug: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.debug(f"Fetching pull requests for repository: {repo_slug}")
        async for data in self._fetch_paginated_data(f"repositories/{workspace}/{repo_slug}/pullrequests"):
            yield data

    async def fetch_components(self, workspace: str, repo_slug: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.debug(f"Fetching components for repository: {repo_slug}")
        async for data in self._fetch_paginated_data(f"repositories/{workspace}/{repo_slug}/components"):
            yield data

    async def register_webhook(self, workspace: str, webhook_url: str, secret: str) -> None:
        url = f"{self.base_url}/workspaces/{workspace}/hooks"
        payload = {
            "description": "Port Ocean Integration Webhook",
            "url": webhook_url,
            "active": True,
            "events": BITBUCKET_EVENTS,
            "secret": secret,
        }
        response = await self.http_client.post(url, json=payload, headers=self.auth_header)
        response.raise_for_status()
        logger.info(f"Webhook registered successfully for workspace {workspace}: {response.json()}")
