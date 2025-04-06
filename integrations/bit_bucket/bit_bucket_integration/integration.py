import asyncio
import logging
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.core.integrations.base import BaseIntegration
from .config import CONFIG
from .auth import CustomAuthClient, get_auth_token

BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"
WORKSPACE = CONFIG.integration.bitbucket.workspace
logger = logging.getLogger(__name__)

class BitbucketOceanIntegration(BaseIntegration):
    """Integration class for Bitbucket API with Ocean Framework."""

    def __init__(self, config):
        super().__init__(config)
        self.auth_token = get_auth_token(
            config.integration.bitbucket.username, 
            config.integration.bitbucket.app_password
        )
        self.client = OceanAsyncClient(
            base_url=BITBUCKET_API_BASE,
            headers={
                "Authorization": f"Basic {self.auth_token}",
                "Content-Type": "application/json"
            }
        )
        self.port_client = self._initialize_port_client()

    def _initialize_port_client(self):
        """Initializes the Port client with exception handling."""
        try:
            return CustomAuthClient()
        except Exception as e:
            logger.warning(f"Failed to initialize Port client: {e}")
            return None

    async def fetch_projects(self):
        """Fetches projects for the workspace."""
        return await self._fetch_paginated_data(f"{BITBUCKET_API_BASE}/workspaces/{WORKSPACE}/projects")

    async def fetch_repositories(self):
        """Fetches repositories for the workspace."""
        return await self._fetch_paginated_data(f"{BITBUCKET_API_BASE}/repositories/{WORKSPACE}")

    async def fetch_pull_requests(self, repo_slug):
        """Fetches pull requests for a specific repository."""
        return await self._fetch_paginated_data(f"{BITBUCKET_API_BASE}/repositories/{WORKSPACE}/{repo_slug}/pullrequests")

    async def _fetch_paginated_data(self, endpoint, max_retries=3):
        """
        Fetches paginated data from the Bitbucket API.

        Implements exponential backoff for handling rate limits.
        """
        results = []
        url = endpoint
        retries = 0

        while url:
            try:
                response = await self.client.get(url)
                response.raise_for_status()

                data = await response.json()
                logger.debug(f"API Response: {data}")

                results.extend(data.get("values", []))
                url = data.get("next", None)

            except Exception as e:
                if retries < max_retries:
                    wait_time = 2 ** retries  # Exponential backoff (2s, 4s, 8s)
                    logger.warning(f"Request error, retrying in {wait_time} seconds... Error: {e}")
                    await asyncio.sleep(wait_time)
                    retries += 1
                else:
                    logger.error(f"Max retries exceeded for {endpoint}. Skipping...")
                    break

        return results

    async def ingest_data_to_port(self):
        """Ingests Bitbucket data into Port."""
        if not self.port_client:
            logger.error("Port client is not initialized.")
            return
        
        try:
            projects = await self.fetch_projects()
            repositories = await self.fetch_repositories()
            pull_requests = []

            for repo in repositories:
                repo_slug = repo.get("slug")
                if repo_slug:
                    pull_requests.extend(await self.fetch_pull_requests(repo_slug))

            logger.info(
                f"Data ingestion completed: {len(projects)} projects, {len(repositories)} repositories, {len(pull_requests)} PRs"
            )

        except Exception as e:
            logger.error(f"Failed to ingest data: {e}")