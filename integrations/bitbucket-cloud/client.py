import httpx
from loguru import logger

from port_ocean.context.ocean import ocean

class BitbucketClient:
    def __init__(self, workspace: str, token: str):
        self.workspace = workspace
        self.token = token
        self.base_url = ocean.integration_config["bitbucket_base_url"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def _fetch_paginated_data(self, endpoint: str) -> list:
        """Helper method to fetch paginated data from Bitbucket API."""
        all_data = []
        url = f"{self.base_url}/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            while url:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                all_data.extend(data.get("values", []))
                
                url = data.get("next", None)
        
        return all_data

    async def fetch_repositories(self) -> list:
        """Fetch all repositories in the workspace."""
        logger.debug(f"Fetching repositories for workspace: {self.workspace}")
        return await self._fetch_paginated_data(f"repositories/{self.workspace}")

    async def fetch_projects(self) -> list:
        """Fetch all projects in the workspace."""
        logger.debug(f"Fetching projects for workspace: {self.workspace}")
        return await self._fetch_paginated_data(f"workspaces/{self.workspace}/projects")

    async def fetch_pull_requests(self, repo_slug: str) -> list:
        """Fetch all pull requests for a repository."""
        logger.debug(f"Fetching pull requests for repository: {repo_slug}")
        return await self._fetch_paginated_data(f"repositories/{self.workspace}/{repo_slug}/pullrequests")

    async def fetch_components(self, repo_slug: str) -> list:
        """Fetch all components for a repository."""
        logger.debug(f"Fetching components for repository: {repo_slug}")
        return await self._fetch_paginated_data(f"repositories/{self.workspace}/{repo_slug}/components")