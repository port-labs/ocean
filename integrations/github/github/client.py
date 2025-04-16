import asyncio
import time
from typing import Any, AsyncGenerator, Dict, Optional, Tuple, List

import httpx
from port_ocean.utils import http_async_client
from loguru import logger
from port_ocean.context.ocean import ocean

ENDPOINT_TEMPLATES = {
    "teams": "/orgs/{org}/teams/{team_slug}",
    "repository": "/repos/{owner}/{repo}",
    "issue": "/repos/{owner}/{repo}/issues/{issue_number}",
    "pull_request": "/repos/{owner}/{repo}/pulls/{pull_number}",
    "workflow_run": "/repos/{owner}/{repo}/actions/runs/{run_id}",
}

GITHUB_EVENTS = [
    "push",
    "pull_request",
    "issues",
    "issue_comment",
    "create",
    "delete",
    "fork",
    "watch",
    "release",
    "public",
    "repository",
    "member",
    "team",
    "workflow_run"
]


class GitHubClient:
    def __init__(
        self, token: str, org: str, base_url: Optional[str] = None, max_retries: int = 3
    ) -> None:
        self.token = token
        self.org = org
        self.base_url = base_url or "https://api.github.com"
        self.client = http_async_client
        self.client.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            }
        )
        self.max_concurrent_requests = 10
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.max_retries = max_retries
        self.webhook_url = f"https://api.github.com/orgs/{self.org}/hooks"

    @staticmethod
    def _handle_rate_limit(response: httpx.Response) -> float:
        if (
            response.status_code in (429, 403)
            and "X-RateLimit-Remaining" in response.headers
        ):
            remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
            if remaining == 0:
                reset_time = int(
                    response.headers.get("X-RateLimit-Reset", time.time() + 60)
                )
                wait_time = max(reset_time - int(time.time()), 1)
                logger.warning(
                    f"Rate limit reached. Waiting {wait_time}s before retrying."
                )
                return wait_time
        return 0.0

    async def _send_api_request(
        self,
        method: str,
        url: str,
        query_params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
    ) -> Tuple[List[Dict[str, Any]], httpx.Response]:
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=json_data,
                )
            wait_time = self._handle_rate_limit(response)
            if wait_time > 0:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Rate-limited {wait_time:.1f}s; retry {attempt}/{self.max_retries} => {method} {url}"
                    )
                    await asyncio.sleep(wait_time)
                    return await self._send_api_request(
                        method, url, query_params, json_data, attempt + 1
                    )
                else:
                    logger.error(f"Exceeded max retries (rate-limit) => {method} {url}")
                    response.raise_for_status()
            response.raise_for_status()
            json_result = response.json()
            if isinstance(json_result, list):
                return json_result, response
            elif isinstance(json_result, dict):
                return [json_result], response
            else:
                logger.debug(
                    f"Unexpected JSON type: {type(json_result)} => returning empty list"
                )
                return [], response
        except httpx.HTTPError as exc:
            logger.error(
                f"HTTP request error (attempt {attempt}) => {method} {url}: {str(exc)}"
            )
            if attempt < self.max_retries:
                logger.warning(
                    f"Retrying (attempt {attempt + 1} of {self.max_retries})"
                )
                return await self._send_api_request(
                    method, url, query_params, json_data, attempt + 1
                )
            raise

    async def get_paginated(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        url = f"{self.base_url}{endpoint}"
        while url:
            page_list, resp = await self._send_api_request(
                "GET", url, query_params=params
            )
            yield page_list
            link_header = resp.headers.get("Link", "")
            url = self._extract_next_url(link_header)

    @staticmethod
    def _extract_next_url(header: str) -> Optional[str]:
        for part in header.split(","):
            if 'rel="next"' in part:
                url_segment = part.split(";")[0].strip()
                return url_segment.strip("<>")
        return None

    async def get_organization_repos(
        self
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        endpoint = f"/orgs/{self.org}/repos"
        async for repo in self.get_paginated(endpoint):
            yield repo


    async def get_pull_requests(
        self, repo: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        endpoint = f"/repos/{self.org}/{repo}/pulls"
        async for pr in self.get_paginated(endpoint):
            yield pr


    async def get_issues(
        self, repo: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        endpoint = f"/repos/{self.org}/{repo}/issues"
        async for issue in self.get_paginated(endpoint):
            yield issue


    async def get_workflows(
        self, repo: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        endpoint = f"/repos/{self.org}/{repo}/actions/workflows"
        async for workflow in self.get_paginated(endpoint):
            yield workflow


    async def get_teams(
        self
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        endpoint = f"/orgs/{self.org}/teams"
        async for team in self.get_paginated(endpoint):
            yield team

    async def fetch_single_github_resource(
        self, resource_type: str, **kwargs
    ) -> AsyncGenerator[List[Dict], None]:
        if resource_type not in ENDPOINT_TEMPLATES:
            logger.error(f"Unknown resource type: {resource_type}")
            return
        endpoint_template = ENDPOINT_TEMPLATES[resource_type]
        endpoint = endpoint_template.format(**kwargs)
        try:
            async for page_list in self.get_paginated(endpoint):
                yield page_list
        except httpx.HTTPError as exc:
            logger.warning(f"Failed to fetch {resource_type} => {kwargs}: {str(exc)}")
            return

    async def create_github_webhook(self, app_host: str) -> None:
        webhook_target = f"{app_host}/integration/webhook"
        await self._ensure_webhook_exists(self.webhook_url, webhook_target, "GitHub organization")
        github_repo = ocean.integration_config.get("github_repo")
        if github_repo:
            repo_hooks_url = f"https://api.github.com/repos/{self.org}/{github_repo}/hooks"
            await self._ensure_webhook_exists(repo_hooks_url, webhook_target, "GitHub repository")


    async def _ensure_webhook_exists(self, webhooks_url: str, webhook_target: str, webhook_type: str) -> None:
        hooks, resp = await self._send_api_request("GET", url=webhooks_url)
        for hook in hooks:
            if hook.get("config", {}).get("url") == webhook_target:
                logger.info(f"{webhook_type} webhook already exists")
                return
        body = {
            "name": "web",
            "active": True,
            "events": GITHUB_EVENTS,
            "config": {
                "url": webhook_target,
                "content_type": "json",
                "secret": ocean.integration_config.get("github_webhook_secret", "default_secret"),
                "insecure_ssl": "0"
            }
        }
        await self._send_api_request("POST", webhooks_url, json_data=body)
        logger.info(f"{webhook_type} webhook created")