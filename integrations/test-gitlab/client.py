import os
import logging
from typing import Any, Dict, List
from port_ocean.utils import http_async_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load configuration values
GITLAB_API_URL = os.getenv("OCEAN__INTEGRATION__CONFIG__GITLAB_API_URL")
GITLAB_TOKEN = os.getenv("OCEAN__INTEGRATION__CONFIG__GITLAB_TOKEN")

logging.basicConfig(level=logging.INFO)

class GitLabHandler:
    def __init__(self, api_url: str = GITLAB_API_URL, token: str = GITLAB_TOKEN) -> None:
        self.api_url = api_url
        self.token = token

        if not self.token:
            logging.error("GITLAB_TOKEN is missing. Please set it in the environment.")
            raise ValueError("GITLAB_TOKEN is required for GitLab API access")

    async def _request(self, endpoint: str) -> List[Dict[str, Any]]:
        """Make a single request to the GitLab API without pagination."""
        url = f"{self.api_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await http_async_client.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    async def fetch_groups(self) -> List[Dict[str, Any]]:
        """Fetch top-level groups from GitLab without recursion."""
        logging.info("Fetching groups from GitLab...")
        endpoint = "/groups"
        data = await self._request(endpoint)
        
        return [
            {
                "identifier": group["id"],
                "name": group["name"],
                "url": group["web_url"],
                "description": group.get("description"),
                "visibility": group.get("visibility"),
            }
            for group in data
        ]
