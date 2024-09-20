import asyncio
import httpx
from typing import List, Dict, Any, AsyncIterator
from loguru import logger
from port_ocean.context.ocean import ocean

class GitLabClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        logger.info(f"GitLabClient initialized with base_url: {self.base_url}")

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint}"
        logger.info(f"Making {method} request to {url}")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=self.headers, timeout=60, **kwargs)
                logger.info(f"Response received from {url} with status code {response.status_code}")
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    logger.error(f"Permission denied for endpoint: {url}")
                elif exc.response.status_code == 404:
                    logger.error(f"Resource not found: {url}")
                else:
                    logger.error(f"Error occurred during request: {exc}")
                return {}
            
            # Handle rate limiting
            if 'RateLimit-Remaining' in response.headers and int(response.headers['RateLimit-Remaining']) == 0:
                reset_time = int(response.headers.get('RateLimit-Reset', 60))
                logger.warning(f"Rate limit exceeded, sleeping for {reset_time} seconds")
                await asyncio.sleep(reset_time)

            return response.json()

    async def get_groups(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch groups from GitLab."""
        endpoint = "groups"
        logger.info("Fetching groups from GitLab")
        async for page in self._paginated_request("GET", endpoint):
            logger.info(f"Fetched page with {len(page)} groups")
            yield page

    async def get_merge_requests(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch merge requests from GitLab."""
        endpoint = "merge_requests"
        logger.info("Fetching merge requests from GitLab")
        async for page in self._paginated_request("GET", endpoint):
            logger.info(f"Fetched page with {len(page)} merge requests")
            yield page

    async def get_issues(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch issues from GitLab."""
        endpoint = "issues"
        logger.info("Fetching issues from GitLab")
        async for page in self._paginated_request("GET", endpoint):
            logger.info(f"Fetched page with {len(page)} issues")
            yield page

    async def get_projects(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Fetch projects from GitLab that belong to the access token's owner."""
        endpoint = "projects"
        params = {"owned": "true"}  # Use params to pass query parameters
        logger.info("Fetching projects owned by the authenticated user from GitLab")
        async for page in self._paginated_request("GET", endpoint, params=params):
            logger.info(f"Fetched page with {len(page)} projects")
            yield page

    async def get_single_merge_request(self, mr_id: int) -> Dict[str, Any]:
        """Fetch a single merge request by ID."""
        endpoint = f"merge_requests/{mr_id}"
        logger.info(f"Fetching merge request with ID {mr_id}")
        merge_request = await self._request("GET", endpoint)
        logger.info(f"Fetched merge request: {merge_request}")
        return merge_request

    async def get_single_issue(self, issue_id: int) -> Dict[str, Any]:
        """Fetch a single issue by ID."""
        endpoint = f"issues/{issue_id}"
        logger.info(f"Fetching issue with ID {issue_id}")
        issue = await self._request("GET", endpoint)
        logger.info(f"Fetched issue: {issue}")
        return issue

    async def setup_webhook(self, app_host: str, webhook_token: str) -> None:
        """Setup GitLab webhook for a project."""
        project_id = ocean.integration_config.get("project_id")
        if not project_id:
            logger.warning("Missing project_id, skipping webhook setup.")
            return

        # List existing webhooks and check for duplication
        endpoint = f"projects/{project_id}/hooks"
        logger.info(f"Checking for existing webhooks for project {project_id}")
        existing_hooks = await self._request("GET", endpoint)

        webhook_url = f"{app_host}/webhook"
        for hook in existing_hooks:
            if hook.get("url") == webhook_url:
                logger.info(f"Webhook already exists for {webhook_url}. Skipping creation.")
                return

        # Set up a new webhook if none exists
        payload = {
            "url": webhook_url,
            "token": webhook_token,
            "push_events": True,
            "merge_requests_events": True,
            "issues_events": True,
        }
        logger.info(f"Setting up webhook for project {project_id} at {webhook_url}")
        await self._request("POST", endpoint, json=payload)
        logger.info("Webhook setup completed")

    async def _paginated_request(self, method: str, endpoint: str, per_page: int = 100, **kwargs) -> AsyncIterator[List[Dict[str, Any]]]:
        """Helper function to handle paginated requests."""
        page = 1
        while True:
            logger.info(f"Fetching page {page} of {endpoint}")
            response = await self._request(method, f"{endpoint}?page={page}&per_page={per_page}", **kwargs)
            if not response:
                logger.info("No more data to fetch.")
                break

            yield response

            if len(response) < per_page:
                logger.info("Fetched final page.")
                break

            page += 1
