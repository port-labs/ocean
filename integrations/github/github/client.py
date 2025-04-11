"""
github/client.py
----------------
A GitHub client based on Ocean’s custom async HTTP client utilities.
This client handles GitHub API communication including pagination and rate‐limit handling.
"""

import asyncio
import time
import os
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from port_ocean.utils import http_async_client
from loguru import logger

WEBHOOK_EVENTS = ["branch_protection_rule", "check_run", "check_suite", "code_scanning_alert", "commit_comment", "create", "delete", "dependabot_alert", "deploy_key", "deployment", "deployment_status", "discussion", "discussion_comment", "fork", "github_app_authorization", "gollum", "installation", "installation_repositories", "issue_comment", "issues", "label", "marketplace_purchase", "member", "membership", "merge_group", "meta", "milestone", "organization", "org_block", "package", "page_build", "ping", "project", "project_card", "project_column", "public", "pull_request", "pull_request_review", "pull_request_review_comment", "pull_request_review_thread", "push", "release", "repository", "repository_dispatch", "repository_import", "repository_vulnerability_alert", "secret_scanning_alert", "security_advisory", "sponsorship", "star", "status", "team", "team_add", "watch", "workflow_dispatch", "workflow_job", "workflow_run"]

class GitHubClient:
    def __init__(self, token: str, org: str, repo: str, base_url: Optional[str] = None) -> None:
        self.token = token
        self.org = org
        self.base_url = base_url or "https://api.github.com"
        self.client = http_async_client
        self.client.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        })
        self.repo = repo
        self.max_concurrent_requests = 10
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.webhook_url = f"https://api.github.com/repos/{self.org}/{self.repo}/hooks"


    @staticmethod
    def _handle_rate_limit(response: httpx.Response) -> float:
        """Determine if the response indicates a rate limit, and return the wait time in seconds."""
        if response.status_code in (429, 403) and "X-RateLimit-Remaining" in response.headers:
            remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
            if remaining == 0:
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait_time = max(reset_time - int(time.time()), 1)
                logger.warning(f"Rate limit reached. Waiting for {wait_time} seconds before retrying.")
                return wait_time
        return 0.0

    async def _request(self, method: str, url: str, json: Optional[Dict[str, str]] = None) -> Any:
        try:
            async with self._semaphore:
                response = await self.client.request(method, url, json=json)
        except httpx.HTTPError as exc:
            logger.error(f"HTTP request failed: {method} {url} - {exc}")
            raise

        wait_time = self._handle_rate_limit(response)
        if wait_time:
            await asyncio.sleep(wait_time)
            # After waiting, retry the request recursively.
            return await self._request(method, url, json)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(f"Request to {url} failed with status {exc.response.status_code}")
            raise

        return response

    async def get(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        return await self._request("GET", url, params)

    async def get_paginated(
        self, endpoint: str, params: Optional[Dict[str, str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        url = f"{self.base_url}{endpoint}"
        while url:
            response = await self._request("GET", url, params)
            data = response.json()
            for item in data:
                yield item
            url = self._extract_next_page(response)
            params = None

    @staticmethod
    def _extract_next_page(response: httpx.Response) -> Optional[str]:
        """Extracts the URL for the next page from the Link header."""
        link = response.headers.get("Link")
        if not link:
            return None
        for part in link.split(","):
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip()
                return url_part.strip("<>")
        return None

    async def create_webhooks(self, app_host: str) -> None:
        await self._create_events_webhook(app_host)

    async def _create_events_webhook(self, app_host: str) -> None:
        # The target URL for the webhook endpoint.
        webhook_target = f"{app_host}/integration/webhook"

        # Retrieve the list of existing webhooks from GitHub.
        webhooks = await self._request("GET", url=self.webhook_url)

        # Check if a webhook with the same target URL already exists.
        for hook in webhooks.json():
            if hook.get("config", {}).get("url") == webhook_target:
                logger.info("GitHub webhook already exists")
                return

        # Prepare the request payload according to GitHub's API.
        # See: https://docs.github.com/en/rest/webhooks/repos?apiVersion=2022-11-28#create-a-repository-webhook
        body = {
            "name": "web",
            "active": True,
            "events": WEBHOOK_EVENTS,  # e.g., ["push", "pull_request"]; define this constant accordingly
            "config": {
                "url": webhook_target,
                "content_type": "json",
                "insecure_ssl": "0",
                "secret": os.getenv("GITHUB_WEBHOOK_SECRET")
            }
        }

        # Create the new webhook using a POST request.
        await self._request("POST", self.webhook_url, json=body)
        logger.info("GitHub webhook created")

    async def fetch_repositories(self) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch all repositories for the organization.
        """
        async for repo in self.get_paginated(f"/orgs/{self.org}/repos"):
            yield repo

    async def fetch_pull_requests(self, repo_name: str) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch pull requests for a specific repository.
        """
        async for pr in self.get_paginated(f"/repos/{self.org}/{repo_name}/pulls"):
            yield pr

    async def fetch_issues(self, repo_name: str) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch issues for a specific repository.
        """
        async for issue in self.get_paginated(f"/repos/{self.org}/{repo_name}/issues"):
            yield issue

    async def fetch_teams(self) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch teams for the organization.
        """
        async for team in self.get_paginated(f"/orgs/{self.org}/teams"):
            yield team

    async def fetch_workflows(self, repo_name: str) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch workflows for a specific repository.
        """
        response = await self.get(f"/repos/{self.org}/{repo_name}/actions/workflows")
        data = response.json()
        for workflow in data.get("workflows", []):
            yield workflow

    async def fetch_files(self, repo_name: str) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch contents (files/folders) for a specific repository.
        """
        response = await self.get(f"/repos/{self.org}/{repo_name}/contents")
        data = response.json()
        for item in data:
            yield item


    async def fetch_workflow_run(self, repo_owner: str, repo_name: str, run_id: str) -> Optional[dict]:
        """
        Fetch full details about a GitHub Actions workflow run.
        Returns the JSON data if successful, or None if an error occurs.
        """
        endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
        response = await self.get(endpoint)

        if response.status_code == 200:
            logger.debug(f"Successfully fetched workflow run {run_id} for {repo_owner}/{repo_name}.")
            return response.json()
        else:
            logger.warning(
                f"Failed to fetch workflow run {run_id} for {repo_owner}/{repo_name}: "
                f"{response.status_code} - {response.text}"
            )
            return None


    async def fetch_team(self, org: str, team_slug: str) -> Optional[dict]:
        """
        Retrieve a team's details from GitHub by its slug and org.
        https://docs.github.com/en/rest/teams/teams#get-a-team-by-name
        Endpoint: GET /orgs/{org}/teams/{team_slug}
        """
        endpoint = f"/orgs/{org}/teams/{team_slug}"
        response = await self.get(endpoint)

        if response.status_code == 200:
            logger.debug(f"Successfully fetched team {team_slug} for org {org}.")
            return response.json()
        else:
            logger.warning(
                f"Failed to fetch team {team_slug} for org {org}: "
                f"{response.status_code} - {response.text}"
            )
            return None

    async def fetch_repository(self, owner: str, repo_name: str) -> Optional[dict]:
        """
        Fetch a repository's full details by owner and name.
        Endpoint: GET /repos/{owner}/{repo}
        https://docs.github.com/en/rest/repos/repos#get-a-repository
        """
        endpoint = f"/repos/{owner}/{repo_name}"
        response = await self.get(endpoint)

        if response.status_code == 200:
            repo_data = response.json()
            logger.debug(
                f"Successfully fetched repository '{repo_name}' for owner '{owner}'."
            )
            return repo_data
        else:
            logger.warning(
                f"Failed to fetch repository '{repo_name}' for owner '{owner}': "
                f"{response.status_code} - {response.text}"
            )
            return None


    async def fetch_commit(self, owner: str, repo: str, commit_sha: str) -> Optional[dict]:
        """
        Fetch full commit details from GitHub's commits endpoint.
        https://docs.github.com/en/rest/commits/commits#get-a-commit
        """
        endpoint = f"/repos/{owner}/{repo}/commits/{commit_sha}"
        response = await self.get(endpoint)

        if response.status_code == 200:
            commit_data = response.json()
            logger.debug(f"Successfully fetched commit {commit_sha} in {owner}/{repo}.")
            return commit_data
        else:
            logger.warning(
                f"Failed to fetch commit {commit_sha} in {owner}/{repo}: "
                f"{response.status_code} - {response.text}"
            )
            return None

    async def fetch_pull_request(self, owner: str, repo: str, pull_number: int) -> Optional[dict]:
        """
        Fetch a pull request by its number in a given repository.
        https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request
        Endpoint: GET /repos/{owner}/{repo}/pulls/{pull_number}
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/{pull_number}"
        response = await self.get(endpoint)

        if response.status_code == 200:
            pr_data = response.json()
            logger.debug(f"Successfully fetched PR #{pull_number} in {owner}/{repo}.")
            return pr_data
        else:
            logger.warning(
                f"Failed to fetch PR #{pull_number} in {owner}/{repo}: "
                f"{response.status_code} - {response.text}"
            )
            return None


    async def fetch_issue(self, owner: str, repo: str, issue_number: int) -> Optional[dict]:
        """
        Fetch an issue by owner, repo, and issue number.
        https://docs.github.com/en/rest/issues/issues#get-an-issue
        Endpoint: GET /repos/{owner}/{repo}/issues/{issue_number}
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}"
        response = await self.get(endpoint)

        if response.status_code == 200:
            issue_data = response.json()
            logger.debug(f"Successfully fetched issue #{issue_number} in {owner}/{repo}.")
            return issue_data
        else:
            logger.warning(
                f"Failed to fetch issue #{issue_number} in {owner}/{repo}: "
                f"{response.status_code} - {response.text}"
            )
            return None

