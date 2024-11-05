import httpx
from abc import ABC, abstractmethod
from typing import Any
from loguru import logger

# Constants for rate limiting
_DEFAULT_RATE_LIMIT_QUOTA: int = 60  # Default quota for API calls
MAXIMUM_CONCURRENT_REQUESTS: int = 10  # Max concurrent requests

class GitLabAPIQuota(ABC):
    """
    GitLabAPIQuota is an abstract base class designed to fetch and manage quota information for GitLab API requests.
    It provides core logic to interact with the GitLab API, ensuring that the application stays within the allocated limits.
    This abstraction supports extending the class for different GitLab resources.
    """

    access_token: str
    gitlab_host: str
    quota_id: str | None = None
    _default_quota: int = _DEFAULT_RATE_LIMIT_QUOTA

    def __init__(self, gitlab_host: str, access_token: str):
        self.access_token = access_token
        self.gitlab_host = gitlab_host

    async def _request_api(self, endpoint: str) -> Any:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.gitlab_host}/{endpoint}", headers={"Bearer": self.access_token})
            response.raise_for_status()
            return response.json()

    async def _get_quota(self) -> int:
        logger.info(f"Using default quota of {self._default_quota} for API calls.")
        return self._default_quota

    @abstractmethod
    def quota_name(self) -> str:
        """Generate the fully qualified name for the quota resource."""
        pass
