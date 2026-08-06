# integrations/github/github/client.py
import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, List, Dict, Optional

import httpx
import yaml
from httpx import Timeout
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

MAX_CONCURRENT_REQUESTS = 10
PAGE_SIZE = 100

class GitHubClient:
    """
    GitHub API client following SOLID principles:
    - Single Responsibility: Handles API interactions only.
    - Open-Closed: Extensible for new methods without modifying existing.
    - Liskov Substitution: Can be subclassed if needed.
    - Interface Segregation: Focused on GitHub-specific methods.
    - Dependency Inversion: Depends on abstractions (http client).
    """

    def __init__(
        self,
        base_url: str = "https://api.github.com",
        token: str = "",
        org_name: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.org_name = org_name
        self.token = token
        self.webhook_secret = webhook_secret
        self.client = http_async_client
        self.client.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Ocean-GitHub-Integration",
            }
        )
        self.client.timeout = Timeout(30)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def flatten_folders(
        self,
        node: Dict, parent_path: str = "", repo_id: int = 0, repo_full_name: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator to flatten folder tree recursively, yielding one folder at a time.
        """
        for name, data in node.items():
            if name == "_meta":
                continue
            full_path = f"{parent_path}/{name}" if parent_path else name
            meta = data.get("_meta", {})
            folder_data = {
                 "path": full_path,
                "sha": meta.get("sha"),
                "url": meta.get("url"),
                "type": meta.get("type"),
                "repository_id": repo_id,
                "repository_full_name": repo_full_name,
                "parent_path": parent_path  # For self-relation
            }
            # Fetch README concurrently (non-blocking)
            try:
                readme_task = asyncio.create_task(self._send_api_request("GET", f"repos/{repo_full_name}/contents/{full_path}/README.md"))
                readme_data = await asyncio.wait_for(readme_task, timeout=5.0)
                if readme_data and "content" in readme_data:
                    decoded = base64.b64decode(readme_data["content"]).decode("utf-8")
                    folder_data["readme"] = decoded
                else:
                    folder_data["readme"] = ""
            except (asyncio.TimeoutError, httpx.HTTPStatusError, KeyError):
                folder_data["readme"] = ""  # Default on error/404
            yield folder_data  # Yield single folder

            # Recurse: Yield from subfolders (generator propagation)
            if isinstance(data, dict) and len(data) > 1:  # Has sub-items
                async for sub_folder in self.flatten_folders(data, full_path, repo_id, repo_full_name):
                    yield sub_folder

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        etag: Optional[str] = None,
    ) -> Any:
        """
        Centralized request handler with rate limiting, retries, and conditional requests.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method, url=url, params=params, json=json, headers=headers
                )
                # Check rate limit
                remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                if remaining < 100:
                    logger.warning(f"Low rate limit remaining: {remaining}")
                if response.status_code == 304:
                    return None  # Not modified
                response.raise_for_status()
                if response.content:
                    return response.json()
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
                await asyncio.sleep(retry_after)
                return await self._send_api_request(method, endpoint, params, json, etag)
            logger.error(
                f"HTTP error {e.response.status_code} for {url}: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {str(e)}")
            raise

    async def get_rate_limit(self) -> Dict[str, Any]:
        """Fetch current rate limit status."""
        return await self._send_api_request("GET", "rate_limit")

    async def get_paginated(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, etag: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Generic pagination handler with conditional requests.
        """
        params = params or {}
        params["per_page"] = PAGE_SIZE
        page = 1
        while True:
            current_params = {**params, "page": page}
            data = await self._send_api_request("GET", endpoint, params=current_params, etag=etag)
            if data is None or not isinstance(data, list) or len(data) == 0:
                break
            yield data
            page += 1

    async def get_repositories(self, etag: Optional[str] = None) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch repositories, enriching with README if possible.
        """
        if self.org_name:
            endpoint = f"orgs/{self.org_name}/repos"
        else:
            endpoint = "user/repos"
        async for batch in self.get_paginated(endpoint, etag=etag):
            enriched_batch = []
            for repo in batch:
                try:
                    readme_data = await self._send_api_request(
                        "GET", f"repos/{repo['full_name']}/readme"
                    )
                    if readme_data:
                        repo["readme"] = base64.b64decode(readme_data.get("content", b"")).decode("utf-8")
                    else:
                        repo["readme"] = ""
                except httpx.HTTPStatusError as e:
                    if e.response.status_code != 404:
                        logger.warning(f"Failed to fetch README for {repo['full_name']}: {str(e)}")
                    repo["readme"] = ""
                enriched_batch.append(repo)
            yield enriched_batch

    async def get_pull_requests(
        self, repo_full_name: str, statuses: List[str], since: str, etag: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch and filter pull requests for a repository.
        """
        params = {"state": "all"}
        if since:
            params["since"] = since
        async for batch in self.get_paginated(f"repos/{repo_full_name}/pulls", params, etag=etag):
            filtered = []
            for pr in batch:
                pr_status = "merged" if pr["merged_at"] else pr["state"]
                if pr_status in statuses:
                    filtered.append(pr)
            if filtered:
                yield filtered

    async def get_issues(
        self, repo_full_name: str, statuses: List[str], since: str, etag: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch and filter issues for a repository.
        """
        params = {"state": "all"}
        if since:
            params["since"] = since
        async for batch in self.get_paginated(f"repos/{repo_full_name}/issues", params, etag=etag):
            filtered = [i for i in batch if not i.get("pull_request") and i["state"] in statuses]
            if filtered:
                yield filtered

    async def get_file_content(self, repo_full_name: str, path: str) -> Dict[str, Any]:
        """
        Fetch file content and parse if applicable.
        """
        content_data = await self._send_api_request("GET", f"repos/{repo_full_name}/contents/{path}")
        if not content_data:
            return {}
        parsed = None
        try:
            decoded = base64.b64decode(content_data["content"]).decode("utf-8")
            if path.endswith(".json"):
                parsed = json.loads(decoded)
            elif path.endswith((".yaml", ".yml")):
                parsed = yaml.safe_load(decoded)
        except Exception as e:
            logger.warning(f"Failed to parse {path} in {repo_full_name}: {str(e)}")
        return {
            "path": path,
            "content": content_data["content"],
            "parsed_content": parsed,
            "html_url": content_data["html_url"],
            "sha": content_data["sha"],
            "repository_full_name": repo_full_name,
        }

    async def get_files(
        self,
        repo_full_name: str,
        repo_id: int,
        default_branch: str,
        extensions: List[str],
        paths: Optional[List[str]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch files from repository default branch, filtering and batching.
        Handles truncation by warning and processing available files.
        """
        tree_url = f"repos/{repo_full_name}/git/trees/{default_branch}?recursive=1"
        tree_response = await self._send_api_request("GET", tree_url)
        if not tree_response:
            return
        if tree_response.get("truncated"):
            logger.warning(f"Tree truncated for {repo_full_name}; consider using Git LFS or pagination for large repos.")
        file_paths = [
            item["path"]
            for item in tree_response.get("tree", [])
            if item["type"] == "blob"
            and (not extensions or any(item["path"].endswith(ext) for ext in extensions))
            and (not paths or any(item["path"].startswith(p) for p in paths))
        ]
        batch_size = 10  # To respect rate limits
        for i in range(0, len(file_paths), batch_size):
            batch_paths = file_paths[i : i + batch_size]
            tasks = [
                self.get_file_content(repo_full_name, path)
                for path in batch_paths
            ]
            batch = await asyncio.gather(*tasks, return_exceptions=True)
            valid_batch = [f for f in batch if not isinstance(f, Exception) and f]
            for f in valid_batch:
                f["repository_id"] = repo_id
            if valid_batch:
                yield valid_batch
    
    # Add to the end of the GitHubClient class in github/client.py

    async def get_folders(
        self,
        repo_full_name: str,
        repo_id: int,
        default_branch: str,
        paths: Optional[List[str]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch folders from repository default branch, filtering by paths and enriching with README.
        Yields batches of folders (e.g., 50 per batch) for resync efficiency.
        """
        tree_url = f"repos/{repo_full_name}/git/trees/{default_branch}?recursive=1"
        tree_response = await self._send_api_request("GET", tree_url)
        if not tree_response or tree_response.get("truncated"):
            logger.warning(f"Tree truncated for {repo_full_name}; large repo detected.")
            return

        # Build folder tree from items
        folder_tree = {}
        for item in tree_response.get("tree", []):
            if item["type"] == "tree":  # Folder
                full_path = item["path"]
                if not paths or any(full_path.startswith(p.rstrip('/')) for p in paths):
                    parts = full_path.split('/')
                    current = folder_tree
                    for part in parts[:-1]:  # Parent folders
                        current = current.setdefault(part, {})
                    current = current.setdefault(parts[-1], {})
                    current["_meta"] = {
                        "sha": item["sha"],
                        "url": item["url"],
                        "type": "folder"
                    }

        # Flatten and yield in batches
        all_folders: List[Dict[str, Any]] = []
        async for folder in self.flatten_folders(folder_tree, repo_id=repo_id, repo_full_name=repo_full_name):
            all_folders.append(folder)
            if len(all_folders) >= 50:  # Batch size
                yield all_folders
                all_folders = []

        # Yield remaining
        if all_folders:
            yield all_folders

    async def has_webhook_permission(self) -> bool:
        """
        Check if token has webhook permissions by attempting to list hooks.
        """
        try:
            if self.org_name:
                await self._send_api_request("GET", f"orgs/{self.org_name}/hooks")
            else:
                # For user, check a repo or general permission
                await self._send_api_request("GET", "user")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [403, 404]:
                logger.warning("Insufficient permissions for webhooks.")
            return False

    async def create_webhooks(self, app_host: str) -> None:
        """
        Create webhooks for real-time updates on repositories or organization.
        Requires admin:repo_hook or equivalent fine-grained permission.
        """
        if not await self.has_webhook_permission():
            logger.warning("Insufficient permissions to create webhooks.")
            return

        webhook_url = f"{app_host}/integration/webhook"
        config = {
            "name": "ocean-github-webhook",
            "active": True,
            "events": ["pull_request", "issues", "push"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "insecure_ssl": "0",
            },
        }

        if self.org_name:
            # Org-level webhook
            endpoint = f"orgs/{self.org_name}/hooks"
            existing = await self._send_api_request("GET", endpoint)
            if existing and any(h["config"]["url"] == webhook_url for h in existing):
                logger.info("Organization webhook already exists.")
                return
            await self._send_api_request("POST", endpoint, json=config)
            logger.info("Created organization webhook.")
        else:
            # Repo-level: Create for each repo
            async for repos in self.get_repositories():
                for repo in repos:
                    repo_endpoint = f"repos/{repo['full_name']}/hooks"
                    existing = await self._send_api_request("GET", repo_endpoint)
                    if existing and any(h["config"]["url"] == webhook_url for h in existing):
                        logger.info(f"Webhook already exists for {repo['full_name']}.")
                        continue
                    repo_config = config.copy()
                    await self._send_api_request("POST", repo_endpoint, json=repo_config)
                    logger.info(f"Created webhook for {repo['full_name']}.")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature for security.
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured; skipping verification.")
            return True
        expected = hmac.new(
            self.webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)