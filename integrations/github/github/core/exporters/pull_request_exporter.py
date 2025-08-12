from typing import Any
from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):
    MAX_CLOSED_PR_AGE_DAYS = 60  # only include closed PRs updated in last 60 days
    MAX_CLOSED_PULL_REQUESTS_TO_EXPORT = 100
    CLOSED_PULL_REQUESTS_PER_PAGE = 100

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name, params = extract_repo_params(dict(options))
        pr_number = params["pr_number"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls/{pr_number}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched pull request with identifier: {repo_name}/{pr_number}")

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name, extras = extract_repo_params(dict(options))
        states = extras["states"]
        max_results = extras["max_results"]

        logger.info(f"Starting pull request export for repository {repo_name}")

        if "open" in states:
            async for open_batch in self._fetch_open_pull_requests(
                repo_name, {"state": "open"}
            ):
                yield open_batch

        if "closed" in states:
            async for closed_batch in self._fetch_closed_pull_requests(
                repo_name, max_results
            ):
                yield closed_batch

    def _build_pull_request_paginated_endpoint(self, repo_name: str) -> str:
        return (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/pulls"
        )

    async def _fetch_open_pull_requests(
        self, repo_name: str, params: dict[str, Any]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(repo_name)

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            logger.info(
                f"Fetched batch of {len(pull_requests)} open pull requests from repository {repo_name}"
            )
            batch = [enrich_with_repository(pr, repo_name) for pr in pull_requests]
            yield batch

    async def _fetch_closed_pull_requests(
        self, repo_name: str, max_results: int
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(repo_name)
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
        }

        total_count = 0
        logger.info(
            f"[Closed PRs] Starting fetch for closed pull requests of repository {repo_name} "
            f"with max_results={max_results}"
        )

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            if not pull_requests:
                logger.info(
                    f"[Closed PRs] No more closed pull requests returned for repository {repo_name}; stopping."
                )
                break

            remaining = max_results - total_count
            if remaining <= 0:
                break

            # Trim batch if it would exceed max_results
            limited_batch = pull_requests[:remaining]
            batch_count = len(limited_batch)

            logger.info(
                f"[Closed PRs] Fetched closed pull requests batch of {batch_count} from {repo_name} "
                f"(total so far: {total_count + batch_count}/{max_results})"
            )

            yield [enrich_with_repository(pr, repo_name) for pr in limited_batch]
            total_count += batch_count
