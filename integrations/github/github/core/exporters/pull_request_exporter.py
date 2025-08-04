from datetime import UTC, datetime, timedelta
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
        """Get pull requests in the organization's repositories with pagination."""

        repo_name, params = extract_repo_params(dict(options))
        include_closed = params.get("include_closed", False)

        logger.info(
            f"Starting export for repository {repo_name} (include_closed={include_closed})"
        )

        async for open_batch in self._fetch_open_pull_requests(repo_name, params):
            yield open_batch

        if include_closed:
            async for closed_batch in self._fetch_closed_pull_requests(repo_name):
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
        self, repo_name: str
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(repo_name)
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
        }

        max_batches = (
            self.MAX_CLOSED_PULL_REQUESTS_TO_EXPORT
            // self.CLOSED_PULL_REQUESTS_PER_PAGE
        )
        batch_count = 0

        logger.info(
            f"[Closed PRs] Starting fetch (max_batches={max_batches}, cutoff_days={self.MAX_CLOSED_PR_AGE_DAYS})"
        )

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            if not pull_requests:
                logger.info(
                    "[Closed PRs] No more PRs returned for repository {repo_name}; stopping."
                )
                break

            if batch_count >= max_batches:
                logger.info(
                    f"[Closed PRs] Reached batch limit ({max_batches}) for repository {repo_name}; stopping."
                )
                break

            filtered = self._filter_prs_by_updated_at(pull_requests)
            if not filtered:
                logger.info(
                    f"[Closed PRs] All PRs in batch filtered out by updated_at cutoff for repository {repo_name}; stopping."
                )
                break

            logger.info(
                f"[Closed PRs] Batch {batch_count} from {repo_name}: {len(filtered)} PRs after filtering"
            )
            yield [enrich_with_repository(pr, repo_name) for pr in filtered]
            batch_count += 1

    def _filter_prs_by_updated_at(
        self, prs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(days=self.MAX_CLOSED_PR_AGE_DAYS)

        return [
            pr
            for pr in prs
            if datetime.strptime(pr["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=UTC
            )
            >= cutoff
        ]
