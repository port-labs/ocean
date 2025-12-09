from typing import Any, cast
from datetime import datetime

from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListPullRequestOptions, SinglePullRequestOptions
from github.helpers.gql_queries import (
    LIST_PULL_REQUESTS_GQL,
    PULL_REQUEST_DETAILS_GQL,
)
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
)
from github.core.exporters.pull_request_exporter.utils import filter_prs_by_updated_at
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


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

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name, organization, extras = parse_github_options(dict(options))
        states = extras["states"]
        max_results = extras["max_results"]
        updated_after = extras["updated_after"]

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
                organization, cast(str, repo_name), max_results, updated_after
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
                enrich_with_organization(
                    enrich_with_repository(pr, repo_name), organization
                )
                for pr in pull_requests
            ]
            yield batch

    async def _fetch_closed_pull_requests(
        self,
        organization: str,
        repo_name: str,
        max_results: int,
        updated_after: datetime,
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
                enrich_with_organization(
                    enrich_with_repository(pr, repo_name), organization
                )
                for pr in filter_prs_by_updated_at(
                    limited_batch, "updated_at", updated_after
                )
            ]

            yield enriched_batch

            total_count += batch_count


class GraphQLPullRequestExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        repo_name, organization, params = parse_github_options(dict(options))
        pr_number: int = params["pr_number"]
        repo = params["repo"]

        variables = {
            "organization": organization,
            "repo": repo_name,
            "prNumber": pr_number,
        }
        payload = self.client.build_graphql_payload(
            PULL_REQUEST_DETAILS_GQL,
            variables,
        )

        logger.info(f"[GraphQL] Fetching PR {organization}/{repo_name}#{pr_number}")
        response = await self.client.send_api_request(
            self.client.base_url,
            method="POST",
            json_data=payload,
        )

        if not response:
            logger.warning(
                f"[GraphQL] PR {organization}/{repo_name}#{pr_number} not found"
            )
            return {}

        pr_node = response["data"]["repository"]["pullRequest"]
        return self._normalize_pr_node(pr_node, repo, organization)

    async def get_paginated_resources[
        self, ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        repo_name, organization, extras = parse_github_options(dict(options))
        states = extras["states"]
        max_results = extras["max_results"]
        updated_after = extras["updated_after"]
        repo = extras["repo"]

        if "open" in states:
            async for batch in self._fetch_open_pull_requests(
                organization, repo, ["OPEN"]
            ):
                yield batch

        if "closed" in states:
            async for batch in self._fetch_closed_pull_requests(
                organization, repo, max_results, updated_after
            ):
                yield batch

    async def _fetch_open_pull_requests(
        self, organization: str, repo: dict[str, Any], states: list[str]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Generic fetcher used for both open and closed (without updated_after/max_results)."""

        repo_name = repo["name"]
        variables = {
            "organization": organization,
            "repo": repo_name,
            "states": states,
            "__path": "repository.pullRequests",
        }

        log_prefix = "open" if "OPEN" in states else "closed"
        logger.info(
            f"[GraphQL] Fetching {log_prefix} PRs from {organization}/{repo_name}"
        )

        async for pr_nodes in self.client.send_paginated_request(
            LIST_PULL_REQUESTS_GQL,
            variables,
        ):
            if not pr_nodes:
                continue

            batch = [
                self._normalize_pr_node(pr_node, repo, organization)
                for pr_node in pr_nodes
            ]

            logger.info(f"[GraphQL] Yielding batch of {len(batch)} {log_prefix} PRs")
            yield batch

    async def _fetch_closed_pull_requests(
        self,
        organization: str,
        repo: dict[str, Any],
        max_results: int,
        updated_after: datetime,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:

        repo_name = repo["name"]
        variables = {
            "organization": organization,
            "repo": repo_name,
            "states": ["CLOSED"],
            "__path": "repository.pullRequests",
        }

        total_count = 0
        async for pr_nodes in self.client.send_paginated_request(
            LIST_PULL_REQUESTS_GQL,
            variables,
        ):
            if not pr_nodes:
                logger.info(
                    f"No more closed pull requests returned for repository {repo_name} from {organization}; stopping."
                )
                break

            remaining = max_results - total_count
            if remaining <= 0:
                break

            limited_batch = pr_nodes[:remaining]
            batch_count = len(limited_batch)

            logger.info(
                f"Fetched closed pull requests batch of {batch_count} from {repo_name} from {organization} "
                f"(total so far: {total_count + batch_count}/{max_results})"
            )

            enriched_batch = [
                self._normalize_pr_node(pr, repo, organization)
                for pr in filter_prs_by_updated_at(
                    limited_batch, "updatedAt", updated_after
                )
            ]

            yield enriched_batch

            total_count += batch_count

    def _normalize_pr_node(
        self, pr_node: dict[str, Any], repo: dict[str, Any], organization: str
    ) -> dict[str, Any]:
        """Centralized normalization — used by ALL code paths."""

        repo_name = repo["name"]
        normalized = {
            **pr_node,
            "assignees": pr_node["assignees"]["nodes"],
            "reviewRequests": pr_node["reviewRequests"]["nodes"],
            "labels": pr_node["labels"]["nodes"],
            "requested_reviewers": self._extract_requested_reviewers(pr_node),
            "comments": pr_node["comments"]["totalCount"],
            "review_comments": pr_node["reviewThreads"]["totalCount"],
            "commits": pr_node["commits"]["totalCount"],
            "state": pr_node["state"].lower(),
            "mergeable_state": pr_node["mergeStateStatus"].lower(),
            "mergeable": True if pr_node["mergeable"] == "MERGEABLE" else False,
            "__repository_object": repo,
        }

        return enrich_with_organization(
            enrich_with_repository(normalized, repo_name), organization
        )

    def _extract_requested_reviewers(
        self, pr_node: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract both users and teams from reviewRequests."""
        reviewers = []
        nodes = pr_node["reviewRequests"]["nodes"]
        for node in nodes:
            reviewer = node["requestedReviewer"]
            typ = reviewer["__typename"]

            if not reviewer:
                continue
            if typ == "User":
                reviewers.append({"login": reviewer["login"], "type": typ})
            elif typ == "Team":
                reviewers.append(
                    {"name": reviewer["name"], "slug": reviewer["slug"], "type": typ}
                )
        return reviewers
