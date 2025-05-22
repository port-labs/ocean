import os
import logging
import asyncio
import time
import typing as t

from port_ocean.utils import http_async_client
from httpx import (
    HTTPStatusError,
    RequestError,
)

from .types import (
    GithubRepo,
    GithubPullRequest,
    GithubIssue,
    GithubTeam,
    GithubWorkflow,
)

from .errors import (
    GithubError,
    GithubRateLimitError,
    GithubNotFoundError,
    GithubAPIError,
)


logger = logging.getLogger(__name__)


class GithubClient:
    DEFAULT_BASE_URL = "https://api.github.com"
    DEFAULT_API_VERSION = "2022-11-28"
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_FACTOR = 2  # seconds

    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str = DEFAULT_API_VERSION,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ):
        if not token:
            raise ValueError("GitHub token cannot be empty")
        self.token = token
        self.base_url = base_url
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.api_version = api_version

        self.client = http_async_client

    @property
    def base_headers(self) -> t.Mapping[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.api_version,
        }

    @staticmethod
    def from_env(key: str = "GITHUB_TOKEN") -> "GithubClient":
        token = os.getenv(key)
        if not token:
            logger.error(f'Environment variable "{key}" is not set.')
            raise ValueError(f'Environment variable "{key}" is not set.')

        return GithubClient(token)

    async def _handle_rate_limit_sleep(
        self, response_headers: t.Mapping[str, str]
    ) -> None:
        # Check rate limit headers and sleeps if necessary
        retry_after_str = response_headers.get("Retry-After")
        if retry_after_str:
            try:
                sleep_duration = int(retry_after_str)
                logger.warning(
                    f"Rate limit hit (Retry-After header). Sleeping for {sleep_duration} seconds..."
                )
                await asyncio.sleep(sleep_duration)
                return
            except ValueError:
                logger.warning(f"Invalid Retry-After header value: {retry_after_str}")

        reset_time_str = response_headers.get("X-RateLimit-Reset")
        remaining_str = response_headers.get("X-RateLimit-Remaining")

        if remaining_str and reset_time_str:
            try:
                if int(remaining_str) == 0:
                    reset_timestamp = int(reset_time_str)
                    current_timestamp = int(time.time())
                    sleep_duration = max(0, reset_timestamp - current_timestamp)
                    logger.warning(
                        f"Primary rate limit exceeded. Remaining: 0. Sleeping for {sleep_duration} seconds until {reset_timestamp}"
                    )
                    if sleep_duration > 0:
                        await asyncio.sleep(sleep_duration)

            except ValueError:
                logger.warning(
                    f"Invalid rate limit header values. Remaining: {remaining_str}, Reset: {reset_time_str}"
                )

    async def _make_request(
        self,
        method: str,
        path: str,
        params: t.Optional[t.Dict[str, t.Any]] = None,
        json_data: t.Optional[t.Any] = None,
    ) -> t.Any:
        """
        Makes a request to the GitHub API with error handling, retries, and rate limit awareness.
        """
        # i'm not handling list pagination here

        url = f"{self.base_url}/{path.lstrip('/')}"

        for attempt in range(self.max_retries + 1):
            try:
                # everyything goes well
                logger.debug(
                    f"Request attempt {attempt + 1}/{self.max_retries + 1}: {method} {url} with params {params}"
                )

                response = await self.client.request(
                    method,
                    url,
                    headers=self.base_headers,
                    params=params,
                    json=json_data,
                )

                # cehck for rate limit
                await self._handle_rate_limit_sleep(response.headers)

                # err
                response.raise_for_status()

                # no content
                if response.status_code == 204:
                    return None

                return response.json()

            except HTTPStatusError as e:
                response_data = None
                try:
                    response_data = e.response.json()
                except Exception:
                    response_data = e.response.text

                error_message = f"GitHub API error for {method} {url}: {e.response.status_code} - {str(response_data)[:200]}"
                logger.error(error_message, exc_info=False)

                if e.response.status_code == 401:
                    raise GithubAPIError(
                        f"Unauthorized: Invalid GitHub token or insufficient permissions. {str(response_data)[:200]}",
                        e.response.status_code,
                        response_data,
                    ) from e
                if e.response.status_code == 403:
                    reset_time_str = e.response.headers.get("X-RateLimit-Reset")
                    reset_time = (
                        int(reset_time_str)
                        if reset_time_str and reset_time_str.isdigit()
                        else None
                    )

                    is_rate_limit_error_primary = "rate limit exceeded" in str(
                        response_data
                    ).lower() or (
                        e.response.headers.get("X-RateLimit-Remaining") == "0"
                    )
                    is_rate_limit_error_secondary = (
                        "secondary rate limit" in str(response_data).lower()
                    )

                    if is_rate_limit_error_primary or is_rate_limit_error_secondary:
                        error_type = (
                            "Primary" if is_rate_limit_error_primary else "Secondary"
                        )
                        logger.warning(
                            f"{error_type} rate limit exceeded for {url}. Reset time: {reset_time}. Details: {str(response_data)[:200]}"
                        )
                        if attempt < self.max_retries:
                            await self._handle_rate_limit_sleep(e.response.headers)
                            sleep_duration = self.backoff_factor * (2**attempt)
                            logger.info(
                                f"Retrying after {error_type.lower()} rate limit sleep and additional backoff of {sleep_duration}s..."
                            )
                            await asyncio.sleep(sleep_duration)
                            continue
                        else:
                            raise GithubRateLimitError(
                                f"{error_type} rate limit exceeded after multiple retries. {str(response_data)[:200]}",
                                reset_time,
                            ) from e
                    raise GithubAPIError(
                        f"Forbidden: Access denied. {str(response_data)[:200]}",
                        e.response.status_code,
                        response_data,
                    ) from e
                elif e.response.status_code == 404:
                    raise GithubNotFoundError(
                        f"Resource not found: {url}. {str(response_data)[:200]}",
                        e.response.status_code,
                        response_data,
                    ) from e
                elif e.response.status_code == 429:
                    # GitHub sometimes uses 403 for primary RL
                    logger.warning(
                        f"Rate limit (429 Too Many Requests) for {url}. {str(response_data)[:200]}"
                    )
                    if attempt < self.max_retries:
                        await self._handle_rate_limit_sleep(e.response.headers)
                        sleep_duration = self.backoff_factor * (2**attempt)
                        logger.info(
                            f"Retrying after 429 sleep and additional backoff of {sleep_duration}s..."
                        )
                        await asyncio.sleep(sleep_duration)
                        continue
                    else:
                        raise GithubRateLimitError(
                            f"Rate limit (429) hit after retries. {str(response_data)[:200]}"
                        ) from e
                elif e.response.status_code >= 500:
                    if attempt < self.max_retries:
                        sleep_duration = self.backoff_factor * (2**attempt)
                        logger.warning(
                            f"Server error ({e.response.status_code}) for {url}. Retrying in {sleep_duration}s... Attempt {attempt + 1}/{self.max_retries + 1}"
                        )
                        await asyncio.sleep(sleep_duration)
                        continue
                    else:
                        raise GithubAPIError(
                            f"GitHub server error after multiple retries. {str(response_data)[:200]}",
                            e.response.status_code,
                            response_data,
                        ) from e
                else:
                    raise GithubAPIError(
                        f"Unhandled GitHub API error. {str(response_data)[:200]}",
                        e.response.status_code,
                        response_data,
                    ) from e

            except RequestError as e:
                error_msg = f"Network error making request to {method} {url}: {str(e)}"
                logger.error(error_msg)
                if attempt < self.max_retries:
                    sleep_duration = self.backoff_factor * (2**attempt)
                    logger.warning(
                        f"Network error for {url}. Retrying in {sleep_duration}s... Attempt {attempt + 1}/{self.max_retries + 1}"
                    )
                    await asyncio.sleep(sleep_duration)
                    continue
                else:
                    raise GithubError(
                        f"Max retries reached for network error: {error_msg}"
                    ) from e
            except Exception as e:
                error_msg = f"An unexpected error occurred during the request to {method} {url}: {str(e)}"
                logger.exception(error_msg)
                raise GithubError(error_msg) from e

        raise GithubError(
            f"Failed to make request to {method} {url} after {self.max_retries + 1} attempts."
        )

    async def get_repositories(self) -> list[GithubRepo]:
        """
        Get all repositories for the authenticated user.
        Note: This fetches the first page of repositories. For all repositories, pagination is needed.
        """
        logger.info("Fetching repositories for the authenticated user")
        try:
            data = await self._make_request(
                "GET", "user/repos", params={"per_page": 100}
            )
            if data is None:
                logger.warning(
                    "Received no data for user repositories, returning empty list."
                )
                return []
            logger.info(f"Successfully retrieved {len(data)} repositories (first page)")
            return t.cast(list[GithubRepo], data)
        except GithubError as e:
            logger.error(f"Failed to fetch repositories: {str(e)}")
            raise

    async def get_pull_requests(self, owner: str, repo: str) -> list[GithubPullRequest]:
        """
        Get all pull requests (open and closed) for a repository.
        Note: This fetches the first page of pull requests. For all pull requests, pagination is needed.
        """
        logger.info(f"Fetching pull requests for {owner}/{repo}")
        try:
            data = await self._make_request(
                "GET",
                f"repos/{owner}/{repo}/pulls",
                params={"state": "all", "per_page": 100},
            )
            if data is None:
                logger.warning(
                    f"Received no data for pull requests in {owner}/{repo}, returning empty list."
                )
                return []
            logger.info(
                f"Successfully retrieved {len(data)} pull requests for {owner}/{repo} (first page)"
            )
            return t.cast(list[GithubPullRequest], data)
        except GithubError as e:
            logger.error(f"Failed to fetch pull requests for {owner}/{repo}: {str(e)}")
            raise

    async def get_issues(self, owner: str, repo: str) -> list[GithubIssue]:
        """
        Get all issues (open and closed) for a repository.
        Note: This fetches the first page of issues. For all issues, pagination is needed.
        """
        logger.info(f"Fetching issues for {owner}/{repo}")
        try:
            data = await self._make_request(
                "GET",
                f"repos/{owner}/{repo}/issues",
                params={"state": "all", "per_page": 100},
            )
            if data is None:
                logger.warning(
                    f"Received no data for issues in {owner}/{repo}, returning empty list."
                )
                return []
            logger.info(
                f"Successfully retrieved {len(data)} issues for {owner}/{repo} (first page)"
            )
            return t.cast(list[GithubIssue], data)
        except GithubError as e:
            logger.error(f"Failed to fetch issues for {owner}/{repo}: {str(e)}")
            raise

    async def get_teams(self, org: str) -> list[GithubTeam]:
        """
        Get all teams for an organization.
        Note: This fetches the first page of teams. For all teams, pagination is needed.
        """
        logger.info(f"Fetching teams for organization {org}")
        try:
            data = await self._make_request(
                "GET", f"orgs/{org}/teams", params={"per_page": 100}
            )
            if data is None:
                logger.warning(
                    f"Received no data for teams in organization {org}, returning empty list."
                )
                return []
            logger.info(
                f"Successfully retrieved {len(data)} teams for {org} (first page)"
            )
            return t.cast(list[GithubTeam], data)
        except GithubError as e:
            logger.error(f"Failed to fetch teams for {org}: {str(e)}")
            raise

    async def get_workflows(self, owner: str, repo: str) -> list[GithubWorkflow]:
        """
        Get all workflows for a repository.
        Note: This fetches the first page of workflows. For all workflows, pagination is needed.
        """
        logger.info(f"Fetching workflows for {owner}/{repo}")
        try:
            data = await self._make_request(
                "GET",
                f"repos/{owner}/{repo}/actions/workflows",
                params={"per_page": 100},
            )
            if data is None or "workflows" not in data:
                logger.warning(
                    f"Received no or malformed workflow data for {owner}/{repo}, returning empty list."
                )
                return []

            # data.get already handles if 'workflows' is missing
            workflows = data.get("workflows", [])
            logger.info(
                f"Successfully retrieved {len(workflows)} workflows for {owner}/{repo} (first page)"
            )
            return t.cast(list[GithubWorkflow], workflows)
        except GithubError as e:
            logger.error(f"Failed to fetch workflows for {owner}/{repo}: {str(e)}")
            raise
