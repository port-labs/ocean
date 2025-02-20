import asyncio
import logging
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.core.integrations.base import BaseIntegration
from .config import CONFIG
from .auth import CustomAuthClient, get_auth_token

BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"
WORKSPACE = CONFIG.integration.bitbucket.workspace

class BitbucketOceanIntegration(BaseIntegration):
    def __init__(self, config):
        super().__init__(config)
        auth_token = get_auth_token(
            config.integration.bitbucket.username, 
            config.integration.bitbucket.app_password
        )
        self.client = OceanAsyncClient(base_url=BITBUCKET_API_BASE, headers={
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json"
        })
        self.port_client = self._initialize_port_client()

    def _initialize_port_client(self):
        try:
            return CustomAuthClient()
        except Exception as e:
            logging.warning(f"Failed to initialize Port client: {e}")
            return None

    async def fetch_projects(self):
        return await self._fetch_paginated_data(f"{BITBUCKET_API_BASE}/workspaces/{WORKSPACE}/projects")

    async def fetch_repositories(self):
        return await self._fetch_paginated_data(f"{BITBUCKET_API_BASE}/repositories/{WORKSPACE}")

    async def fetch_pull_requests(self, repo_slug):
        return await self._fetch_paginated_data(f"{BITBUCKET_API_BASE}/repositories/{WORKSPACE}/{repo_slug}/pullrequests")

    async def _fetch_paginated_data(self, endpoint):
        results = []
        url = endpoint
        while url:
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json() if callable(getattr(response, "json", None)) else response
                logging.debug(f"API Response: {data}")
                results.extend(data.get("values", []))
                url = data.get("next", None)
            except Exception as e:
                logging.warning(f"Request error, retrying after 10 seconds... Error: {e}")
                await asyncio.sleep(10)
        return results

    async def ingest_data_to_port(self):
        if not self.port_client:
            logging.error("Port client is not initialized.")
            return
        
        try:
            projects = await self.fetch_projects()
            repositories = await self.fetch_repositories()
            pull_requests = []
            for repo in repositories:
                repo_slug = repo.get("slug")
                if repo_slug:
                    pull_requests.extend(await self.fetch_pull_requests(repo_slug))

            logging.info(f"Data ingestion simulated: {len(projects)} projects, {len(repositories)} repositories, {len(pull_requests)} PRs")
        except Exception as e:
            logging.error(f"Failed to ingest data: {e}")
