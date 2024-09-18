import httpx
from typing import List, Dict, Any, AsyncIterator
from loguru import logger
from port_ocean.context.ocean import ocean

class GitLabClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()  # Raise error for non-2xx status
            return response.json()

    async def get_groups(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch groups from GitLab."""
        endpoint = "groups"
        async for page in self._paginated_request("GET", endpoint):
            yield page

    async def get_merge_requests(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch merge requests from GitLab."""
        endpoint = "merge_requests"
        async for page in self._paginated_request("GET", endpoint):
            yield page

    async def get_issues(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch issues from GitLab."""
        endpoint = "issues"
        async for page in self._paginated_request("GET", endpoint):
            yield page

    async def get_projects(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch projects from GitLab."""
        endpoint = "projects"
        async for page in self._paginated_request("GET", endpoint):
            yield page

    async def get_single_merge_request(self, mr_id: int) -> Dict[str, Any]:
        """Fetch a single merge request by ID."""
        endpoint = f"merge_requests/{mr_id}"
        return await self._request("GET", endpoint)

    async def get_single_issue(self, issue_id: int) -> Dict[str, Any]:
        """Fetch a single issue by ID."""
        endpoint = f"issues/{issue_id}"
        return await self._request("GET", endpoint)

    async def setup_webhook(self, app_host: str, webhook_token: str) -> None:
        """Setup GitLab webhook for a project."""
        project_id = ocean.integration_config.get("project_id")
        if not project_id:
            logger.warning("Missing project_id, skipping webhook setup.")
            return
        endpoint = f"projects/{project_id}/hooks"
        webhook_url = f"{app_host}/webhook"
        payload = {
            "url": webhook_url,
            "token": webhook_token,
            "push_events": True,
            "merge_requests_events": True,
            "issues_events": True,
        }
        await self._request("POST", endpoint, json=payload)

    async def _paginated_request(self, method: str, endpoint: str, per_page: int = 100, **kwargs) -> AsyncIterator[List[Dict[str, Any]]]:
        """Helper function to handle paginated requests."""
        page = 1
        while True:
            response = await self._request(method, f"{endpoint}?page={page}&per_page={per_page}", **kwargs)
            if not response:
                break 

            yield response

            if len(response) < per_page:
                break

            page += 1
