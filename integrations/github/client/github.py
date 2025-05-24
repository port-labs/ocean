from typing import Any, AsyncGenerator, Optional, ClassVar
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean
from httpx import Response, HTTPError, HTTPStatusError
from port_ocean.utils.cache import cache_iterator_result

PAGE_SIZE: ClassVar[int] = 100  # GitHub API max items per page

class GitHubClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._token = token
        self._base_url = base_url
        self._client = http_async_client
        self._client.follow_redirects = True

    @classmethod
    def from_ocean_configuration(cls) -> "GitHubClient":
        """Create a GitHubClient instance from Ocean configuration.
        
        Returns:
            GitHubClient: A new client instance configured with values from ocean.integration_config
        """
        return cls(
            base_url=ocean.integration_config["github_base_url"],
            token=ocean.integration_config["github_token"]
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github+json"
        }

    async def send_request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        timeout: int = 30
    ) -> Response | None:
        request_headers = {**(headers or {}), **self._headers()}
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                data=data,
                params=params,
                headers=request_headers,
                timeout=timeout
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if response.status_code == 404:
                logger.warning(f"Couldn't access url: {url}. Failed due to 404 error")
                return None
            elif response.status_code == 401:
                logger.error(f"Couldn't access url {url}. Make sure the GitHub token is valid!")
                raise e
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for url {url}. Consider implementing rate limiting.")
                raise e
            else:
                logger.error(f"Request failed with status code {response.status_code}: {method} to url {url}")
                raise e
        except HTTPError as e:
            logger.error(f"Couldn't send request {method} to url {url}: {str(e)}")
            raise e
        return response

    async def _get_paginated(self, url: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {"per_page": PAGE_SIZE}
        current_url = f"{self._base_url}/{url}"

        while True:
            response = await self.send_request("GET", current_url, params=params)
            if not response:
                break

            data = response.json()
            items: list[dict[str, Any]] = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items", [])

            if items:
                logger.info(f"Found {len(items)} objects in url {current_url}")
                yield items

            # Handle GitHub Link header pagination
            link_header = response.headers.get("link")
            if not link_header:
                break

            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip()[1:-1]
                    break

            if not next_url:
                break

            current_url = next_url

    @cache_iterator_result()
    async def get_repositories(self, org: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repositories in self._get_paginated(f"orgs/{org}/repos"):
            yield repositories

    @cache_iterator_result()
    async def get_issues(self, org: str, repo: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for issues in self._get_paginated(f"repos/{org}/{repo}/issues"):
            yield issues

    @cache_iterator_result()
    async def get_pull_requests(self, org: str, repo: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for pull_requests in self._get_paginated(f"repos/{org}/{repo}/pulls"):
            yield pull_requests

    @cache_iterator_result()
    async def get_workflows(self, org: str, repo: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for workflows in self._get_paginated(f"repos/{org}/{repo}/actions/workflows"):
            yield workflows

    @cache_iterator_result()
    async def get_teams(self, org: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self._get_paginated(f"orgs/{org}/teams"):
            yield teams