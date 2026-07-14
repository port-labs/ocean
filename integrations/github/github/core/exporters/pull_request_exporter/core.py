from typing import Any, cast, Optional
from datetime import datetime

from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import (
    ListPullRequestOptions,
    PullRequestGraphQLOptions,
    SinglePullRequestOptions,
)
from github.helpers.gql_queries import (
    EXPENSIVE_PR_GRAPHQL_FIELDS,
    generate_list_pull_requests_gql,
    generate_pull_request_details_gql,
)
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
)
from github.core.exporters.pull_request_exporter.utils import (
    paginate_closed_pull_requests,
)
from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    paginate_with_strategy,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

# PR date-field names as they appear in each API's response payload.
REST_CLOSED_AT_FIELD = "closed_at"
REST_UPDATED_AT_FIELD = "updated_at"
REST_SORT_BY_UPDATED = "updated"
REST_SORT_DIRECTION_DESC = "desc"
GRAPHQL_CLOSED_AT_FIELD = "closedAt"
GRAPHQL_UPDATED_AT_FIELD = "updatedAt"
GRAPHQL_ORDER_BY_UPDATED_AT = "UPDATED_AT"

OPEN_PULL_REQUEST_INCREMENTAL_REST = ClientSideCutoffStrategy(
    stop_field=REST_UPDATED_AT_FIELD,
    query_params={
        "sort": REST_SORT_BY_UPDATED,
        "direction": REST_SORT_DIRECTION_DESC,
    },
)
OPEN_PULL_REQUEST_INCREMENTAL_GRAPHQL = ClientSideCutoffStrategy(
    stop_field=GRAPHQL_UPDATED_AT_FIELD,
)


class RestPullRequestExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT,) -> Optional[RAW_ITEM]:
        repo_name, organization, params = parse_github_options(dict(options))
        pr_number = params["pr_number"]

        endpoint = (
            f"{self.client.base_url}/repos/{organization}/{repo_name}/pulls/{pr_number}"
        )
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No pull request found with number: {pr_number} in repository: {repo_name} from {organization}"
            )
            return None

        logger.debug(
            f"[Rest] Fetched pull request with identifier: {repo_name}/{pr_number} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all pull requests in the organization's repositories with pagination."""

        repo_name, organization, extras = parse_github_options(dict(options))
        incremental_cursor = extras.pop("incremental_cursor", None)
        if incremental_cursor is not None:
            extras["updated_after"] = incremental_cursor
            extras["max_results"] = None
            extras["closed_after"] = None
        states = extras["states"]
        max_results = extras["max_results"]
        updated_after = extras.get("updated_after")
        closed_after = extras.get("closed_after")

        logger.info(
            f"[Rest] Starting pull request export for repository {repo_name} from {organization}"
        )

        if "open" in states:
            logger.info(
                f"[Rest] Fetching open PRs with rest api from {organization}/{repo_name}"
            )
            async for open_batch in self._fetch_open_pull_requests(
                organization, cast(str, repo_name), incremental_cursor
            ):
                yield open_batch

        if "closed" in states:
            logger.info(
                f"[Rest] Fetching closed PRs with rest api from {organization}/{repo_name}"
            )
            async for closed_batch in self._fetch_closed_pull_requests(
                organization,
                cast(str, repo_name),
                None if incremental_cursor is not None else max_results,
                updated_after,
                None if incremental_cursor is not None else closed_after,
            ):
                yield closed_batch

    def _build_pull_request_paginated_endpoint(
        self, organization: str, repo_name: str
    ) -> str:
        return f"{self.client.base_url}/repos/{organization}/{repo_name}/pulls"

    async def _fetch_open_pull_requests(
        self,
        organization: str,
        repo_name: str,
        incremental_cursor: Optional[datetime] = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(organization, repo_name)
        request_params = OPEN_PULL_REQUEST_INCREMENTAL_REST.merge_params(
            {"state": "open"}, incremental_cursor
        )

        async for pull_requests in paginate_with_strategy(
            self.client.send_paginated_request(endpoint, request_params),
            cursor=incremental_cursor,
            strategy=OPEN_PULL_REQUEST_INCREMENTAL_REST,
        ):
            logger.info(
                f"[Rest] Fetched batch of {len(pull_requests)} open pull requests from repository {repo_name} from {organization}"
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
        max_results: Optional[int],
        updated_after: Optional[datetime],
        closed_after: Optional[datetime],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        endpoint = self._build_pull_request_paginated_endpoint(organization, repo_name)
        params = {
            "state": "closed",
            "sort": REST_SORT_BY_UPDATED,
            "direction": REST_SORT_DIRECTION_DESC,
        }

        logger.info(
            f"[Rest] Starting fetch for closed pull requests of repository {repo_name} "
            f"from {organization} with max_results={max_results}"
        )

        cutoff, include_field = (
            (closed_after, REST_CLOSED_AT_FIELD)
            if closed_after is not None
            else (updated_after, REST_UPDATED_AT_FIELD)
        )

        def enrich(pr: dict[str, Any]) -> dict[str, Any]:
            return enrich_with_organization(
                enrich_with_repository(pr, repo_name), organization
            )

        async for batch in paginate_closed_pull_requests(
            self.client.send_paginated_request(endpoint, params),
            enrich=enrich,
            max_results=max_results,
            cutoff=cutoff,
            include_field=include_field,
            stop_field=REST_UPDATED_AT_FIELD,
            log_prefix="[Rest]",
            repo_name=repo_name,
            organization=organization,
        ):
            yield batch


class GraphQLPullRequestExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[
        ExporterOptionsT: SinglePullRequestOptions
    ](self, options: ExporterOptionsT) -> Optional[RAW_ITEM]:
        repo_name, organization, params = parse_github_options(dict(options))
        pr_number: int = params["pr_number"]
        repo = params["repo"]
        pr_gql_options = PullRequestGraphQLOptions(**params)

        variables = {
            "organization": organization,
            "repo": repo_name,
            "prNumber": pr_number,
        }
        payload = self.client.build_graphql_payload(
            generate_pull_request_details_gql(pr_gql_options),
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
            return None

        pr_node = response["data"]["repository"]["pullRequest"]
        return self._normalize_pr_node(
            pr_node,
            repo,
            organization,
            gql_options=pr_gql_options,
        )

    async def get_paginated_resources[
        self, ExporterOptionsT: ListPullRequestOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        _, organization, extras = parse_github_options(dict(options))
        incremental_cursor = extras.pop("incremental_cursor", None)
        if incremental_cursor is not None:
            extras["updated_after"] = incremental_cursor
            extras["max_results"] = None
            extras["closed_after"] = None
        states = extras["states"]
        max_results = extras["max_results"]
        updated_after = extras.get("updated_after")
        closed_after = extras.get("closed_after")
        repo = extras["repo"]
        repo_name = repo["name"]
        pr_gql_options = PullRequestGraphQLOptions(**extras)

        if "open" in states:
            logger.info(
                f"[GraphQL] Fetching open PRs with graphql api from {organization}/{repo_name}"
            )
            async for batch in self._fetch_open_pull_requests(
                organization,
                repo,
                pr_gql_options,
                incremental_cursor,
            ):
                yield batch

        if "closed" in states:
            logger.info(
                f"[GraphQL] Fetching closed PRs from {organization}/{repo_name}"
            )
            async for batch in self._fetch_closed_pull_requests(
                organization,
                repo,
                None if incremental_cursor is not None else max_results,
                updated_after,
                None if incremental_cursor is not None else closed_after,
                pr_gql_options,
            ):
                yield batch

    @staticmethod
    def _build_pr_fallback_queries(
        pr_gql_options: PullRequestGraphQLOptions,
        order_by_field: str = "CREATED_AT",
    ) -> list[str]:
        """Lighter queries to retry with when the full query keeps timing out.

        A single fallback that drops the most expensive per-node fields; empty
        when the user already excludes all of them, so no redundant retry is made.
        """
        already_excluded = set(pr_gql_options.exclude_graphql_fields)
        if all(field in already_excluded for field in EXPENSIVE_PR_GRAPHQL_FIELDS):
            return []
        stripped = generate_list_pull_requests_gql(
            pr_gql_options,
            order_by_field=order_by_field,
            extra_excluded_fields=EXPENSIVE_PR_GRAPHQL_FIELDS,
        )
        return [stripped]

    async def _fetch_open_pull_requests(
        self,
        organization: str,
        repo: dict[str, Any],
        pr_gql_options: PullRequestGraphQLOptions,
        incremental_cursor: Optional[datetime] = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        repo_name = repo["name"]
        order_by_field = (
            GRAPHQL_ORDER_BY_UPDATED_AT
            if incremental_cursor is not None
            else "CREATED_AT"
        )
        variables = {
            "organization": organization,
            "repo": repo_name,
            "states": ["OPEN"],
            "__path": "repository.pullRequests",
        }

        logger.info(f"[GraphQL] Fetching open PRs from {organization}/{repo_name}")

        async for pr_nodes in paginate_with_strategy(
            self.client.send_paginated_request(
                generate_list_pull_requests_gql(
                    pr_gql_options, order_by_field=order_by_field
                ),
                variables,
                fallback_queries=self._build_pr_fallback_queries(pr_gql_options),
            ),
            cursor=incremental_cursor,
            strategy=OPEN_PULL_REQUEST_INCREMENTAL_GRAPHQL,
        ):
            if not pr_nodes:
                continue

            batch = [
                self._normalize_pr_node(
                    pr_node,
                    repo,
                    organization,
                    gql_options=pr_gql_options,
                )
                for pr_node in pr_nodes
            ]

            logger.info(
                f"[GraphQL] Yielding open PRs batch of {len(batch)} from {organization}/{repo_name}"
            )
            yield batch

    async def _fetch_closed_pull_requests(
        self,
        organization: str,
        repo: dict[str, Any],
        max_results: Optional[int],
        updated_after: Optional[datetime],
        closed_after: Optional[datetime],
        pr_gql_options: PullRequestGraphQLOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        repo_name = repo["name"]
        variables = {
            "organization": organization,
            "repo": repo_name,
            "states": ["CLOSED", "MERGED"],
            "__path": "repository.pullRequests",
        }

        logger.info(f"[GraphQL] Fetching closed PRs from {organization}/{repo_name}")

        cutoff, include_field = (
            (closed_after, GRAPHQL_CLOSED_AT_FIELD)
            if closed_after is not None
            else (updated_after, GRAPHQL_UPDATED_AT_FIELD)
        )

        def enrich(pr: dict[str, Any]) -> dict[str, Any]:
            return self._normalize_pr_node(
                pr, repo, organization, gql_options=pr_gql_options
            )

        async for batch in paginate_closed_pull_requests(
            self.client.send_paginated_request(
                generate_list_pull_requests_gql(
                    pr_gql_options, order_by_field=GRAPHQL_ORDER_BY_UPDATED_AT
                ),
                variables,
                fallback_queries=self._build_pr_fallback_queries(
                    pr_gql_options, order_by_field=GRAPHQL_ORDER_BY_UPDATED_AT
                ),
            ),
            enrich=enrich,
            max_results=max_results,
            cutoff=cutoff,
            include_field=include_field,
            stop_field=GRAPHQL_UPDATED_AT_FIELD,
            log_prefix="[GraphQL]",
            repo_name=repo_name,
            organization=organization,
        ):
            yield batch

    def _normalize_pr_node(
        self,
        pr_node: dict[str, Any],
        repo: dict[str, Any],
        organization: str,
        gql_options: PullRequestGraphQLOptions | None = None,
    ) -> dict[str, Any]:
        """Centralized normalization — used by ALL code paths."""

        opts = gql_options or PullRequestGraphQLOptions()
        normalized = {**pr_node}

        if "assignees" in pr_node:
            normalized["assignees"] = pr_node["assignees"].get("nodes", [])

        if "reviewRequests" in pr_node:
            normalized["reviewRequests"] = pr_node["reviewRequests"].get("nodes", [])
            normalized["requested_reviewers"] = self._extract_requested_reviewers(
                pr_node
            )

        if "labels" in pr_node:
            normalized["labels"] = pr_node["labels"].get("nodes", [])

        if "comments" in pr_node:
            normalized["comments"] = pr_node["comments"].get("totalCount")

        if "reviewThreads" in pr_node:
            normalized["review_comments"] = pr_node["reviewThreads"].get("totalCount")

        if "commits" in pr_node:
            normalized["commits"] = pr_node["commits"].get("totalCount")

        if "state" in pr_node:
            normalized["state"] = pr_node["state"].lower() if pr_node["state"] else None

        if "mergeStateStatus" in pr_node:
            normalized["mergeable_state"] = (
                pr_node["mergeStateStatus"].lower()
                if pr_node["mergeStateStatus"]
                else None
            )

        if "mergeable" in pr_node:
            normalized["mergeable"] = pr_node["mergeable"] == "MERGEABLE"

        if opts.enrich_with_first_commit:
            self._enrich_with_first_commit(normalized, pr_node)

        return enrich_with_organization(
            enrich_with_repository(normalized, repo["name"], repo=repo), organization
        )

    def _enrich_with_first_commit(
        self,
        normalized: dict[str, Any],
        pr_node: dict[str, Any],
    ) -> None:
        """Enrich normalized pull request response with data about the first commit."""
        commit_nodes = pr_node["commits"].get("nodes") or []
        if commit_nodes and len(commit_nodes) > 0:
            normalized["firstCommit"] = commit_nodes[0].get("commit") or {}

    def _extract_requested_reviewers(
        self, pr_node: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract both users and teams from reviewRequests."""
        reviewers = []
        nodes = pr_node.get("reviewRequests", {}).get("nodes", [])
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
