from enum import StrEnum
from typing import Any, AsyncGenerator, TypedDict

import httpx
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from loguru import logger
from aiolimiter import AsyncLimiter


class GithubRepositoryTypes(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    ALL = "all"
    FORKS = "forks"
    SOURCES = "sources"


class GithubState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"


WEBHOOK_EVENTS = ["pull_request", "issues"]


class RepoParams(TypedDict):
    type: str


class GitHub:
    """Abstracts away interactions to Github's API.

    The methods are designed to satisfy Ocean's async iterator expectations.
    """

    def __init__(self, token: str | None) -> None:
        self._base_url = "https://api.github.com"
        self._bearer_token = token
        self._http_client = http_async_client
        self._init_rate_limitter()
        logger.info("Github wrapper istantiated.")

    def _init_rate_limitter(self) -> None:
        max_auth_requests = 5000
        max_unauth_requests = 60
        hour = 60 * 60
        if self._bearer_token:
            self.rate_limitter = AsyncLimiter(max_auth_requests, hour)
        else:
            self.rate_limitter = AsyncLimiter(max_unauth_requests, hour)

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github+json",
        }
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
        async with self.rate_limitter:
            try:
                return await self._http_client.request(
                    method, url, params=params, json=json
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"Error occured while fetching {e.request.url}")
                f"status code: {e.response.status_code} - {e.response.text}"
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Could not complete request. unable to fetch {e.request.url} -{e}"
                )
                raise

    async def _get_paginated_data(
        self, url: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        while True:
            res = await self._make_request(url, params=params)
            data = res.json()
            yield data

            pagination = self._extract_pagination_from_header(res.headers)
            if pagination is None:
                break
            # This only handles pagination in "next". I don't know whether going forward and backward is necessary
            url = pagination

    @staticmethod
    def _extract_pagination_from_header(header: httpx.Headers) -> str | None:
        link = header.get("Link", None)
        if link is None:
            return None

        links = link.split(",")

        for link in links:
            url, rel = link.split(";")
            if "next" in rel:
                return url.strip("<> ")

        return None

    @cache_iterator_result()
    async def get_repositories(
        self, owner: str, repo_type: GithubRepositoryTypes = GithubRepositoryTypes.ALL
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in an owner account

        This method will follow pagination until all items have been retrieved

        args:
            owner - Owner of the account, could either be a user or an organization.

        """
        url = f"{self._base_url}/orgs/{owner}/repos"
        logger.info(f"fetching repositories for owner - {owner}")
        async for repositories in self._get_paginated_data(
            url, params={"type": repo_type}
        ):
            yield repositories

    @cache_iterator_result()
    async def get_pull_requests(
        self, owner: str, repo: str, pr_state: GithubState = GithubState.ALL
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch pull requests from a repository

        args:
            owner - Owner of the repository with pull requests, may be a user or an organization
            repo - Repository where PRs should be fetched from
        kwargs:
            pr_state - state of PR to retrieve. By default we'll fetch every PR
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/pulls"
        logger.info(f"fetching pull requests for repository - {repo}")
        async for pull_requests in self._get_paginated_data(
            url, params={"state": pr_state}
        ):
            yield pull_requests

    @cache_iterator_result()
    async def get_issues(
        self, owner: str, repo: str, state: GithubState = GithubState.ALL
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch issues from a repository

        args:
            owner - Owner of the repository with issues, may be a user or an organization
            repo - Repository where issues should be fetched from
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/issues"
        logger.info(f"fetching issues for repository - {repo}")
        async for issues in self._get_paginated_data(url, params={"state": state}):
            yield issues

    async def get_teams(self, org: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        """fetch the teams in an organization.

        args:
            organization - must be an organization
        """
        url = f"{self._base_url}/orgs/{org}/teams"
        logger.info(f"fetching teams in the organization - {org}")
        async for teams in self._get_paginated_data(url):
            yield teams

    async def get_workflows(
        self, owner: str, repo: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """fetch the workflows in repository.

        args:
            owner - workflow owner, can be an organization or a user
            repo - workflow repo - repository where workflows should be fetched from
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/workflows"
        logger.info(f"fetching teams in the organization - {owner}")
        async for workflows in self._get_paginated_data(url):
            yield workflows

    async def register_webhooks(self, app_host: str, owner: str, repo: str) -> None:
        gh_webhook_endpoint = f"{self._base_url}/repos/{owner}/{repo}/hooks"
        webhooks = await self._make_request(gh_webhook_endpoint, "GET")
        port_webhook_url = f"{app_host}/integration/webhook"

        for webhook in webhooks.json():
            if webhook["config"].get("url") == port_webhook_url:
                logger.info("Ocean real time reporting webhook already exists")
                return

        body = {
            "name": f"{ocean.config.integration.identifier}-repo-webhook",
            "events": WEBHOOK_EVENTS,
            "config": {"url": port_webhook_url, "content_type": "json"},
        }

        await self._make_request(gh_webhook_endpoint, "POST", json=body)
        logger.info("Ocean real time reporting webhook created")
