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
        if "per_page" not in params_dict:
            params_dict["per_page"] = self.DEFAULT_PAGE_SIZE

        url = resource_type

        while url:
            logger.debug(f"Fetching from {url}")
            response = await self.send_api_request(
                method="GET",
                path=url,
                params=params_dict if not url.startswith("http") else None,
            )

            if response:
                batch = response.json()
            else:
                break

            if isinstance(batch, list):
                if not batch:
                    break
                yield batch

                links = await self.get_page_links(response)
                url = links.get("next", "")
                params_dict = None
            else:
                items = batch.get("items", []) or batch.get("workflows", [])
                if not items:
                    break
                yield items

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
        try:
            owner, repo_name = repo_path.split('/', 1)
            owner, repo_name = quote(owner, safe=""), quote(repo_name, safe="")
            encoded_file_path = quote(file_path, safe="/")

            path = f"repos/{owner}/{repo_name}/contents/{encoded_file_path}"
            params = {"ref": ref}
            response = await self.send_api_request("GET", path, params=params)
            if not response:
                return None
            response = response.json()
            if "content" in response:
                encoding = response.get("encoding", "")
                raw_content = response["content"]

                if encoding == "base64":
                    clean_content = raw_content.replace("\n", "").replace("\r", "")
                    try:
                        decoded_bytes = base64.b64decode(clean_content)
                        try:
                            return decoded_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            for encoding_attempt in ["latin-1", "cp1252", "iso-8859-1"]:
                                try:
                                    return decoded_bytes.decode(encoding_attempt)
                                except UnicodeDecodeError:
                                    continue
                            return decoded_bytes.decode("utf-8", errors="replace")
                    except Exception as e:
                        logger.error(f"Failed to decode base64 content for {repo_path}/{file_path}: {e}")
                        return None
                elif encoding == "utf-8" or not encoding:
                    return raw_content
                else:
                    logger.warning(f"Unknown encoding '{encoding}' for {repo_path}/{file_path}")
                    return raw_content

            if "download_url" in response and response["download_url"]:
                logger.info(f"File {repo_path}/{file_path} is large, download_url provided")
                return None

            return None

        except ValueError as e:
            logger.error(f"Invalid repo_path format '{repo_path}': {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching file content for {repo_path}/{file_path}: {e}")
            return None

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
