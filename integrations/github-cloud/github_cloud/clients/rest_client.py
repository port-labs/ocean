import base64
from typing import Any, AsyncIterator, Optional, Dict
from urllib.parse import quote
from http import HTTPStatus

from loguru import logger

from github_cloud.clients.base_client import HTTPBaseClient


class RestClient(HTTPBaseClient):
    """GitHub Cloud REST API client for paginated resources and specific endpoints."""

    DEFAULT_PAGE_SIZE = 100

    async def get_paginated_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Fetch a paginated resource from GitHub Cloud API.

        Args:
            resource_type: Resource type/endpoint (e.g., repos, orgs)
            params: Query parameters

        Yields:
            Batches of resources

        Raises:
            Exception: If the API request fails
        """
        params_dict = params or {}
        # GitHub Cloud recommends using per_page parameter
        params_dict["per_page"] = params_dict.get("per_page", self.DEFAULT_PAGE_SIZE)

        url = resource_type

        while url:
            logger.debug(f"Fetching from {url}")
            try:
                response = await self._client.request(
                    method="GET",
                    url=url if url.startswith("http") else f"{self.base_url}/{url}",
                    headers=self._headers,
                    params=params_dict if not url.startswith("http") else None,
                )
                if not response.is_success:
                    logger.error(f"Failed to fetch {url} - Status: {response.status_code}, Content: {response.text}")
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {str(e)}")
                raise

            batch = response.json()

            # Handle different response types using match-case
            match batch:
                case list() if batch:
                    yield batch
                    links = await self.get_page_links(response)
                    url = links.get("next", "")
                    params_dict = None
                case dict() if "items" in batch and batch["items"]:
                    yield batch["items"]
                    # Handle GitHub Cloud search API pagination
                    if "next_page" in batch:
                        params_dict = params_dict or {}
                        params_dict["page"] = batch["next_page"]
                    else:
                        links = await self.get_page_links(response)
                        url = links.get("next", "")
                        params_dict = None
                case _:
                    break

    async def get_paginated_org_resource(
        self,
        org_name: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Fetch a paginated resource for a specific organization.

        Args:
            org_name: Organization name
            resource_type: Resource type (e.g., repos, teams)
            params: Query parameters

        Yields:
            Batches of resources

        Raises:
            Exception: If the API request fails
        """
        path = f"orgs/{org_name}/{resource_type}"
        async for batch in self.get_paginated_resource(path, params=params):
            if batch:
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for org {org_name}"
                )
                yield batch

    async def get_paginated_repo_resource(
        self,
        repo_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Fetch a paginated resource for a specific repository.

        Args:
            repo_path: Repository full name (owner/repo)
            resource_type: Resource type (e.g., issues, pulls)
            params: Query parameters

        Yields:
            Batches of resources

        Raises:
            ValueError: If repo_path is not in the correct format
            Exception: If the API request fails
        """
        try:
            owner, repo = repo_path.split('/', 1)
        except ValueError:
            raise ValueError(f"Invalid repo_path format: {repo_path}. Expected 'owner/repo'")

        encoded_owner = quote(owner, safe="")
        encoded_repo = quote(repo, safe="")
        path = f"repos/{encoded_owner}/{encoded_repo}/{resource_type}"

        async for batch in self.get_paginated_resource(path, params=params):
            if batch:
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for repo {repo_path}"
                )
                yield batch

    async def get_repo_languages(
        self, repo_path: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Get programming languages used in a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            params: Query parameters

        Returns:
            Dictionary of languages and byte counts

        Raises:
            Exception: If the API request fails
        """
        encoded_repo_path = quote(repo_path, safe="")
        path = f"repos/{encoded_repo_path}/languages"
        return await self.send_api_request("GET", path, params=params or {})

    async def get_file_content(
        self, repo_path: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        """
        Get content of a file from a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            file_path: Path to file in the repository
            ref: Git reference (branch, tag, commit)

        Returns:
            File content as string or None if not found

        Raises:
            Exception: If the API request fails
        """
        encoded_repo_path = quote(repo_path, safe="")
        encoded_file_path = quote(file_path, safe="")
        path = f"repos/{encoded_repo_path}/contents/{encoded_file_path}"
        params = {"ref": ref}

        response = await self.send_api_request("GET", path, params=params)
        if not response:
            return None

        # Use ternary operator for cleaner content decoding
        return (
            base64.b64decode(response["content"].replace("\n", "")).decode("utf-8")
            if "content" in response and response.get("encoding") == "base64"
            else None
        )

    async def get_file_data(
        self, repo_path: str, file_path: str, ref: str = "main"
    ) -> dict[str, Any]:
        """
        Get file metadata and content from a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            file_path: Path to file in the repository
            ref: Git reference (branch, tag, commit)

        Returns:
            Dictionary with file data

        Raises:
            Exception: If the API request fails
        """
        encoded_repo_path = quote(repo_path, safe="")
        encoded_file_path = quote(file_path, safe="")
        path = f"repos/{encoded_repo_path}/contents/{encoded_file_path}"
        params = {"ref": ref}

        response = await self.send_api_request("GET", path, params=params)
        if not response:
            return {}

        # Use ternary operator for content decoding
        if "content" in response and response.get("encoding") == "base64":
            response["content"] = base64.b64decode(
                response["content"].replace("\n", "")
            ).decode("utf-8")

        return response

    async def get_page_links(self, response) -> Dict[str, str]:
        """
        Parse GitHub Cloud API pagination links from response headers.

        Args:
            response: The HTTP response

        Returns:
            Dictionary of link relations to URLs
        """
        if "Link" not in response.headers:
            return {}

        return {
            rel.split('rel="')[1].rstrip('"'): parts[0].strip("<>")
            for link in response.headers["Link"].split(",")
            if len(parts := link.strip().split(";")) >= 2
            and 'rel="' in (rel := parts[1].strip())
        }
