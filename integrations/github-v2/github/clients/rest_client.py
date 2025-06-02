from typing import Any, AsyncIterator, Optional, TYPE_CHECKING

from loguru import logger
from port_ocean.utils.cache import cache_iterator_result

from github.clients.base_client import HTTPBaseClient

if TYPE_CHECKING:
    from github.clients.github_client import GitHubClient


class RestClient(HTTPBaseClient):
    DEFAULT_PAGE_SIZE = 100

    def __init__(
        self,
        base_url: str,
        token: str,
        github_client: Optional["GitHubClient"] = None,
    ):
        super().__init__(base_url, token, github_client=github_client)

    async def get_paginated_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated resource (e.g., repos, orgs)."""
        async for batch in self._make_paginated_request(resource_type, params=params):
            yield batch

    async def get_paginated_repo_resource(
        self,
        owner: str,
        repo: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated repository resource (e.g., issues, pulls)."""
        path = f"repos/{owner}/{repo}/{resource_type}"

        async for batch in self._make_paginated_request(path, params=params):
            if batch:
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for repo {owner}/{repo}"
                )
                yield batch

    async def get_paginated_org_resource(
        self,
        org: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch a paginated organization resource (e.g., teams, repos)."""
        path = f"orgs/{org}/{resource_type}"
        async for batch in self._make_paginated_request(path, params=params):
            if batch:
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for org {org}"
                )
                yield batch

    @cache_iterator_result()
    async def _make_paginated_request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        params_dict: dict[str, Any] = params or {}
        if "per_page" not in params_dict:
            params_dict["per_page"] = page_size

        while True:
            request_params = {**params_dict, "page": page}
            logger.debug(f"Fetching page {page} from GitHub API path: {path}")
            response = await self.send_api_request("GET", path, params=request_params)

            # GitHub API returns a list directly, or empty dict for 404
            batch: list[dict[str, Any]] = response if isinstance(response, list) else []
            if not batch:
                break
            yield batch
            if len(batch) < page_size:
                logger.debug(f"Last page reached for {path}, no more data.")
                break
            page += 1
