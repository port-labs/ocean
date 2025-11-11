from datetime import UTC, datetime, timedelta
from typing import Any, Dict, cast
from github.helpers.utils import enrich_with_repository, parse_github_options
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> RAW_ITEM:
        repo_name, organization, params = parse_github_options(dict(options))
        pr_number = params["pr_number"]

        endpoint = (
            f"{self.client.base_url}/repos/{organization}/{repo_name}/pulls/{pr_number}"
        )
        response = await self.client.send_api_request(endpoint)

        logger.debug(
            f"Fetched pull request with identifier: {repo_name}/{pr_number} from {organization}"
        )

        return self._enrich_pull_request_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name, organization, extras = parse_github_options(dict(options))
        states = extras["states"]
        max_results = extras["max_results"]
        since = extras["since"]

        logger.info(
            f"Starting pull request export for repository {repo_name} from {organization}"
        )

        if "open" in states:
            async for open_batch in self._fetch_open_pull_requests(
                organization, cast(str, repo_name), {"state": "open"}
            ):
                yield open_batch

        if "closed" in states:
            async for closed_batch in self._fetch_closed_pull_requests(
                organization, cast(str, repo_name), max_results, since
            ):
                yield closed_batch

    def _build_pull_request_paginated_endpoint(
        self, organization: str, repo_name: str
    ) -> str:
        return f"{self.client.base_url}/repos/{organization}/{repo_name}/pulls"

    async def _fetch_open_pull_requests(
        self, organization: str, repo_name: str, params: dict[str, Any]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(organization, repo_name)

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            logger.info(
                f"Fetched batch of {len(pull_requests)} open pull requests from repository {repo_name} from {organization}"
            )
            batch = [
                self._enrich_pull_request_with_organization(
                    enrich_with_repository(pr, repo_name), organization
                )
                for pr in pull_requests
            ]
            yield batch

    async def _fetch_closed_pull_requests(
        self, organization: str, repo_name: str, max_results: int, since: int
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(organization, repo_name)
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
        }

        total_count = 0
        logger.info(
            f"[Closed PRs] Starting fetch for closed pull requests of repository {repo_name} from {organization} "
            f"with max_results={max_results}"
        )

        async for pull_requests in self.client.send_paginated_request(endpoint, params):
            if not pull_requests:
                logger.info(
                    f"[Closed PRs] No more closed pull requests returned for repository {repo_name} from {organization}; stopping."
                )
                break

            remaining = max_results - total_count
            if remaining <= 0:
                break

            # Trim batch if it would exceed max_results
            limited_batch = pull_requests[:remaining]
            batch_count = len(limited_batch)

            logger.info(
                f"[Closed PRs] Fetched closed pull requests batch of {batch_count} from {repo_name} from {organization} "
                f"(total so far: {total_count + batch_count}/{max_results})"
            )

            enriched_batch = [
                self._enrich_pull_request_with_organization(
                    enrich_with_repository(pr, repo_name), organization
                )
                for pr in self._filter_prs_by_updated_at(limited_batch, since)
            ]

            yield enriched_batch

            total_count += batch_count

    def _filter_prs_by_updated_at(
        self, prs: list[dict[str, Any]], since: int
    ) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(days=since)

        return [
            pr
            for pr in prs
            if datetime.strptime(pr["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=UTC
            )
            >= cutoff
        ]

    def _enrich_pull_request_with_organization(
        self, pr: Dict[str, Any], organization: str
    ) -> Dict[str, Any]:
        """Enrich a pull request with the organization."""
        return {
            **pr,
            "__organization": organization,
        }
