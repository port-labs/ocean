from http import HTTPStatus
from typing import Any, AsyncGenerator, Optional
from loguru import logger
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.base_rotating_client import BaseRotatingClient
from bitbucket_cloud.helpers.exceptions import ClassAttributeNotInitializedError
from httpx import HTTPStatusError, HTTPError

PULL_REQUEST_STATE = "OPEN"
PULL_REQUEST_PAGE_SIZE = 50
PAGE_SIZE = 100


class BitbucketClient(BaseRotatingClient):
    """Client for interacting with Bitbucket Cloud API v2.0."""

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        """
        Create a BitbucketClient instance from Ocean configuration
        """
        instance = cls()
        base_client = BitbucketBaseClient.create_from_ocean_config()
        instance.set_base_client(base_client)
        return instance

    async def _send_paginated_api_request(
        self,
        url: str,
        method: str = "GET",
        return_full_response: bool = False,
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response if return_full_response else response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Requested resource not found: {url}; message: {str(e)}"
                )
                return {}
            logger.error(f"Bitbucket API error: {str(e)}")
            raise e
        except HTTPError as e:
            logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
            raise e

    async def _fetch_paginated_api_with_rate_limiter(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle paginated requests to Bitbucket API."""
        if params is None:
            params = {
                "pagelen": PAGE_SIZE,
            }
        while True:
            try:
                if self.base_client is None:
                    logger.error("Cannot send API request: base_client is None")
                    raise ClassAttributeNotInitializedError(
                        "Base client is not initialized"
                    )

                response = await self.base_client.send_api_request(
                    method=method,
                    url=url,
                    params=params,
                )
                if values := response.get(data_key, []):
                    yield values
                url = response.get("next")
                if not url:
                    break
            except (HTTPStatusError, Exception) as e:
                logger.error(f"Error fetching data from {url}: {str(e)}")
                raise

    async def _send_rate_limited_paginated_api_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Handle paginated requests to Bitbucket API with strict rate limiting.
        This method ensures that a rate limiter is available before making requests.
        """
        if params is None:
            params = {
                "pagelen": PAGE_SIZE,
            }
        while True:
            try:
                await self._ensure_client_available()

                if self.current_limiter is None or self.base_client is None:
                    logger.warning(
                        "Either rate limiter or base client is not initialized"
                    )
                    raise ClassAttributeNotInitializedError(
                        "Rate limiter or base client is not initialized"
                    )

                limiter_id = id(self.current_limiter)
                logger.debug(
                    f"Using client {self.client_id} with limiter {limiter_id} for rate-limited API call to {url}"
                )
                async with self.current_limiter:
                    response = await self.base_client.send_api_request(
                        method=method,
                        url=url,
                        params=params,
                    )
                if values := response.get(data_key, []):
                    yield values
                url = response.get("next")
                if not url:
                    break
            except HTTPError as e:
                if (
                    hasattr(e, "response")
                    and e.response
                    and e.response.status_code == HTTPStatus.TOO_MANY_REQUESTS
                ):
                    logger.warning("Rate limit hit, rotating to next client")
                    await self._rotate_base_client()
                    continue  # Try next client
                logger.error(f"Error while making request: {str(e)}")
                raise  # Re-raise non-rate-limit errors
            except HTTPStatusError as e:
                if hasattr(e, "response") and e.response.status_code != 429:
                    raise
                logger.warning(
                    f"Rate limit exceeded for client {self.client_id}, rotating to next client"
                )
                await self._rotate_base_client()
                continue
            except Exception as e:
                logger.error(f"Error fetching data from {url}: {str(e)}")
                raise

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"{self.base_url}/workspaces/{self.workspace}/projects"
        ):
            logger.info(
                f"Fetched batch of {len(projects)} projects from workspace {self.workspace}"
            )
            yield projects

    @cache_iterator_result()
    async def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_rate_limited_paginated_api_request(
            f"{self.base_url}/repositories/{self.workspace}", params=params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from workspace {self.workspace}"
            )
            yield repos

    async def get_directory_contents(
        self,
        repo_slug: str,
        branch: str,
        path: str,
        max_depth: int,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get contents of a directory."""
        if params is None:
            params = {
                "max_depth": max_depth,
                "pagelen": PAGE_SIZE,
            }
        async for contents in self._fetch_paginated_api_with_rate_limiter(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/src/{branch}/{path}",
            params=params,
        ):
            logger.info(
                f"Fetched directory contents batch with {len(contents)} contents"
            )
            yield contents

    async def _get_pull_requests(
        self, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        params = {
            "state": PULL_REQUEST_STATE,
            "pagelen": PULL_REQUEST_PAGE_SIZE,
        }
        logger.info(
            f"Fetching pull requests for repository {repo_slug} in workspace {self.workspace}"
        )
        async for pull_requests in self._send_rate_limited_paginated_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_slug} in workspace {self.workspace}"
            )
            yield pull_requests
        logger.info(
            f"Finished fetching pull requests for repository {repo_slug} in workspace {self.workspace}"
        )

    async def get_pull_requests(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repositories in self.get_repositories():
            tasks = [
                self._get_pull_requests(repo.get("slug", repo["name"].lower()))
                for repo in repositories
            ]
            logger.info(f"Resyncing pull requests for {len(tasks)} repositories")
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch

    async def get_pull_request(
        self, repo_slug: str, pull_request_id: str
    ) -> dict[str, Any]:
        """Get a specific pull request by ID."""
        if self.base_client is None:
            logger.error("Base client is not initialized")
            raise ClassAttributeNotInitializedError("Base client is not initialized")

        return await self.base_client.send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        )

    async def get_repository(self, repo_slug: str) -> dict[str, Any]:
        """Get a specific repository by slug."""
        if self.base_client is None:
            logger.error("Base client is not initialized")
            raise ClassAttributeNotInitializedError("Base client is not initialized")

        return await self.base_client.send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}"
        )

    async def get_repository_files(self, repo: str, branch: str, path: str) -> Any:
        """Get the content of a file."""
        response = await self._send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo}/src/{branch}/{path}",
            method="GET",
            return_full_response=True,
        )
        logger.info(f"Retrieved file content for {repo}/{branch}/{path}")
        return response.text

    async def search_files(
        self,
        search_query: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Search for files using Bitbucket's search API."""
        params = {
            "pagelen": 300,
            "search_query": search_query,
            "fields": "+values.file.commit.repository.mainbranch.name",
        }

        async for results in self._send_paginated_api_request(
            f"{self.base_url}/workspaces/{self.workspace}/search/code",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(results)} matching files from workspace {self.workspace}"
            )
            yield results
