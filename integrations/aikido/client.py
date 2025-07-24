import base64
import time
from typing import Any, AsyncGenerator, List, Dict, Optional
from httpx import HTTPStatusError, AsyncClient
from loguru import logger
from port_ocean.utils import http_async_client
from helpers.exceptions import MissingIntegrationCredentialException

API_VERSION = "v1"
PAGE_SIZE = 100
ISSUES_ENDPOINT = f"api/public/{API_VERSION}/issues/export"
REPOSITORIES_ENDPOINT = f"api/public/{API_VERSION}/repositories/code"
AUTH_TOKEN_ENDPOINT = "api/oauth/token"
REPO_FIRST_PAGE = 0


class AikidoClient:
    """
    Client for interacting with the Aikido API using OAuth2 client credentials.
    Implements methods to fetch repositories and issues
    """

    def __init__(self, base_url: str, client_id: str, client_secret: str):
        if not client_id or not client_secret:
            raise MissingIntegrationCredentialException(
                "Aikido client ID and secret must be provided."
            )

        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self.http_client: AsyncClient = http_async_client

    async def _generate_oauth_token(self) -> str:
        """
        Generate OAuth token using client credentials flow.
        Returns the access token for API authentication.
        """
        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode("ascii")
            b64_auth = base64.b64encode(auth_bytes).decode("ascii")

            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            data = {"grant_type": "client_credentials"}

            logger.info("Generating OAuth token from Aikido API")
            response = await self.http_client.post(
                f"{self.base_url}/{AUTH_TOKEN_ENDPOINT}",
                headers=headers,
                json=data,
                timeout=30,
            )
            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data["access_token"]
            self._token_expiry = time.time() + token_data.get("expires_in", 3600) - 60

            logger.info("OAuth token generated successfully")
            return self._access_token

        except Exception as e:
            logger.error(f"OAuth token generation failed: {e}")
            raise

    async def _get_valid_token(self) -> str:
        """
        Get a valid access token, generating a new one if needed.
        """
        if (not self._access_token) or (time.time() >= self._token_expiry):
            return await self._generate_oauth_token()
        return self._access_token

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
        token = await self._get_valid_token()
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
                data = await self._send_api_request(endpoint, params=params)
                repos = data if isinstance(data, list) else data.get("repositories", [])

                if not repos:
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
            data = await self._send_api_request(endpoint, params=params)
            if isinstance(data, list):
                return data
            return data.get("issues", [])
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

    async def get_issue_detail(self, issue_id: str) -> Dict[str, Any]:
        """
        Fetch details for a single issue by ID.
        """
        endpoint = f"issues/{issue_id}"
        try:
            return await self._send_api_request(endpoint, method="GET")
        except Exception as e:
            logger.error(f"Error fetching issue detail for {issue_id}: {e}")
            return {}

    async def get_repository_detail(self, repo_id: str) -> Dict[str, Any]:
        """
        Fetch details for a single repository by ID.
        """
        endpoint = f"{REPOSITORIES_ENDPOINT}/{repo_id}"
        try:
            return await self._send_api_request(endpoint, method="GET")
        except Exception as e:
            logger.error(f"Error fetching repository detail for {repo_id}: {e}")
            return {}
