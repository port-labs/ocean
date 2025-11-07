"""Harbor API client implementation."""

import base64
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from port_ocean.utils import http_async_client

from .config import HarborConfig

logger = logging.getLogger(__name__)


class HarborClient:
    """Client for interacting with Harbor API."""

    def __init__(self, config: HarborConfig):
        """
        Initialize HarborClient with configuration.

        Args:
            config (HarborConfig): Configuration for Harbor connection.
        """

        self.config = config
        self.base_url = f"{config.harbor_url.rstrip('/')}/api/v2.0"
        self.auth_header = self._create_auth_header()

    def _create_auth_header(self) -> Dict[str, str]:
        """
        Create the authorization header for Harbor API requests.

        Returns:
            Dict[str, str]: Headers including authorization.
        """

        auth_str = f"{self.config.username}:{self.config.password}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()
        return {
            "Authorization": f"Basic {b64_auth_str}",
            "Content-Type": "application/json",
        }

    async def get_paginated(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Generic method to handle paginated GET requests.
        Args:
            endpoint (str): API endpoint to query.
            params (Optional[Dict[str, Any]]): Query parameters.
        """

        page = 1
        page_size = 100

        while True:
            query_params = {"page": page, "page_size": page_size, **(params or {})}

            try:
                response = await http_async_client.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.auth_header,
                    params=query_params,
                )
                response.raise_for_status()
                data = response.json()
                if not data:
                    break
                yield data
                page += 1
            except Exception as e:
                logger.error("Error fetching paginated data: %s", e)
                break

    async def get_projects(self) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Get all projects from Harbor.
        Yields:
            AsyncGenerator[Dict[str, Any], None]: Project details.
        """

        async for projects in self.get_paginated("/projects"):
            yield projects

    async def get_users(self) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Get all users from Harbor.
        Yields:
            AsyncGenerator[Dict[str, Any], None]: User details.
        """

        async for users in self.get_paginated("/users"):
            yield users

    async def get_repositories(
        self, project_name: Optional[str] = None
    ) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Get all repositories for a given project.

        Args:
            project_name (str): Name of the project to filter repositories.
        Yields:
            AsyncGenerator[Dict[str, Any], None]: Repository details.
        """

        if project_name:
            endpoint = f"/projects/{project_name}/repositories"
        else:
            endpoint = "/repositories"

        async for repos in self.get_paginated(endpoint):
            yield repos

    async def get_artifacts(
        self, project_name: str, repository_name: str
    ) -> AsyncGenerator[list[Dict[str, Any]], None]:
        """
        Get all artifacts for a given repository in a project.

        Args:
            project_name (str): Name of the project.
            repository_name (str): Name of the repository.
        Yields:
            AsyncGenerator[Dict[str, Any], None]: Artifact details.
        """

        if "/" in repository_name:
            repository_name = repository_name.replace("/", "%252F")
        endpoint = f"/projects/{project_name}/repositories/{repository_name}/artifacts"
        params = {
            "with_tag": "true",
            "with_label": "true",
            "with_scan_overview": "true",
        }

        async for artifacts in self.get_paginated(endpoint, params=params):
            yield artifacts
