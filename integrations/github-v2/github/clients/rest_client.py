import base64
from typing import Any, AsyncIterator, Optional, Dict, Union
from urllib.parse import quote, urlparse, parse_qs

from loguru import logger

from github.clients.base_client import HTTPBaseClient


class RestClient(HTTPBaseClient):
    """GitHub REST API client for paginated resources and specific endpoints."""

    DEFAULT_PAGE_SIZE = 100

    async def get_paginated_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Fetch a paginated resource from GitHub API.

        Args:
            resource_type: Resource type/endpoint (e.g., repos, orgs)
            params: Query parameters

        Yields:
            Batches of resources
        """
        params_dict = params or {}
        # GitHub recommends using per_page parameter
        if "per_page" not in params_dict:
            params_dict["per_page"] = self.DEFAULT_PAGE_SIZE

        url = resource_type

        while url:
            logger.debug(f"Fetching from {url}")
            response = await self._client.request(
                method="GET",
                url=url if url.startswith("http") else f"{self.base_url}/{url}",
                headers=self._headers,
                params=params_dict if not url.startswith("http") else None,
            )

            batch = response.json()

            # GitHub returns lists directly for collection endpoints
            if isinstance(batch, list):
                if not batch:
                    break
                yield batch

                # Get next page URL from Link header
                links = await self.get_page_links(response)
                url = links.get("next", "")
                # Clear params since they're included in the next URL
                params_dict = None
            else:
                # Some endpoints return an object with items
                items = batch.get("items", [])
                if not items:
                    break
                yield items

                # Handle GitHub search API pagination which may use different format
                if "next_page" in batch:
                    if params_dict is None:
                        params_dict = {}
                    params_dict["page"] = batch["next_page"]
                else:
                    links = await self.get_page_links(response)
                    url = links.get("next", "")
                    params_dict = None

                if not url and not ("next_page" in batch):
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
        """
        owner, repo = repo_path.split('/', 1)
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
        """
        encoded_repo_path = quote(repo_path, safe="")
        encoded_file_path = quote(file_path, safe="")
        path = f"repos/{encoded_repo_path}/contents/{encoded_file_path}"
        params = {"ref": ref}

        response = await self.send_api_request("GET", path, params=params)
        if not response:
            return None

        # GitHub returns base64 encoded content
        if "content" in response and response.get("encoding") == "base64":
            # GitHub content might include newlines which need to be removed
            content = response["content"].replace("\n", "")
            return base64.b64decode(content).decode("utf-8")

        return None

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
        """
        encoded_repo_path = quote(repo_path, safe="")
        encoded_file_path = quote(file_path, safe="")
        path = f"repos/{encoded_repo_path}/contents/{encoded_file_path}"
        params = {"ref": ref}

        response = await self.send_api_request("GET", path, params=params)
        if not response:
            return {}

        # Convert base64 content if it exists
        if "content" in response and response.get("encoding") == "base64":
            content = response["content"].replace("\n", "")
            response["content"] = base64.b64decode(content).decode("utf-8")

        return response

    async def get_page_links(self, response) -> Dict[str, str]:
        """
        Parse GitHub API pagination links from response headers.

        Args:
            response: The HTTP response

        Returns:
            Dictionary of link relations to URLs
        """
        links = {}

        if "Link" not in response.headers:
            return links

        for link in response.headers["Link"].split(","):
            parts = link.strip().split(";")
            if len(parts) < 2:
                continue

            url = parts[0].strip("<>")
            rel = parts[1].strip()

            if 'rel="' in rel:
                rel_type = rel.split('rel="')[1].rstrip('"')
                links[rel_type] = url

        return links
