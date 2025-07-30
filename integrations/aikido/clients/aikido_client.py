from typing import Any, AsyncGenerator, List, Dict, Optional
from httpx import HTTPStatusError, AsyncClient
from clients.auth_client import AikidoAuth
from loguru import logger
from port_ocean.utils import http_async_client

API_VERSION = "v1"
PAGE_SIZE = 100
ISSUES_ENDPOINT = f"api/public/{API_VERSION}/issues/export"
REPOSITORIES_ENDPOINT = f"api/public/{API_VERSION}/repositories/code"
REPO_FIRST_PAGE = 0


class AikidoClient:
    """
    Client for interacting with the Aikido API using OAuth2 client credentials.
    Implements methods to fetch repositories and issues
    """

    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip("/")
        self.http_client: AsyncClient = http_async_client
        self.auth = AikidoAuth(base_url, client_id, client_secret, self.http_client)

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an authenticated API request to the Aikido API.
        """
        token = await self.auth.get_token()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Requested resource not found: {url}; message: {str(e)}"
                )
                return {}
            logger.error(f"API request failed for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during API request to {url}: {e}")
            raise

    async def get_repositories(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch repositories from the Aikido API.
        Yields batches of repositories as lists of dicts.
        """
        endpoint = REPOSITORIES_ENDPOINT
        params = {"per_page": PAGE_SIZE, "page": REPO_FIRST_PAGE}

        while True:
            try:
                repos = await self._send_api_request(endpoint, params=params)

                if not isinstance(repos, list):
                    break

                if not repos:
                    logger.info(f"No repositories returned for page {params['page']}")
                    break

                logger.info(f"Fetched {len(repos)} repositories from Aikido API")
                yield repos

                if len(repos) < PAGE_SIZE:
                    break

                params["page"] += 1
            except Exception as e:
                logger.error(f"Error fetching repositories: {e}")
                break

    async def get_all_issues(self) -> List[Dict[str, Any]]:
        """
        Fetch all issues from the Aikido API in a single request.
        Returns a list of issue dicts.
        """
        endpoint = ISSUES_ENDPOINT
        params = {"format": "json"}
        try:
            issues = await self._send_api_request(endpoint, params=params)
            if not isinstance(issues, list):
                return []
            return issues
        except Exception as e:
            logger.error(f"Error fetching issues: {e}")
            return []

    async def get_issues_in_batches(
        self, batch_size: int = 100
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch all issues and yield them in batches of the specified size.
        """
        all_issues = await self.get_all_issues()
        for i in range(0, len(all_issues), batch_size):
            yield all_issues[i : i + batch_size]

    async def get_issue(self, issue_id: str) -> Dict[str, Any]:
        """
        Fetch details for a single issue by ID.
        """
        endpoint = f"issues/{issue_id}"
        try:
            return await self._send_api_request(endpoint, method="GET")
        except Exception as e:
            logger.error(f"Error fetching issue detail for {issue_id}: {e}")
            return {}

    async def get_repository(self, repo_id: str) -> Dict[str, Any]:
        """
        Fetch details for a single repository by ID.
        """
        endpoint = f"{REPOSITORIES_ENDPOINT}/{repo_id}"
        try:
            return await self._send_api_request(endpoint, method="GET")
        except Exception as e:
            logger.error(f"Error fetching repository detail for {repo_id}: {e}")
            return {}
