"""Reads the required checks status of open pull requests from GraphQL.

GraphQL flags required checks itself (``isRequired``), so ``GraphQLRequiredChecksEnricher``
only has to read the head commit's check contexts. The reading and reducing of those
lives in ``required_checks``.
"""

import asyncio
from itertools import batched
from typing import Any, Mapping, Optional, Sequence

import httpx
from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.pull_request_exporter.required_checks import (
    PullRequestChecks,
    RequiredChecksSummary,
    apply_required_checks,
    parse_pull_request_node,
    summarize_required_checks,
)
from github.helpers.exceptions import (
    GraphQLClientError,
    GraphQLErrorGroup,
    GraphQLForbiddenFieldError,
    RateLimitException,
)
from github.helpers.gql_queries import (
    REQUIRED_CHECKS_CONTEXTS_PAGE_SIZE,
    generate_pull_requests_required_checks_gql,
    required_checks_alias,
)

GRAPHQL_PRS_PER_QUERY = 5
# Page sizes of the check contexts to try when GitHub rejects the query as too heavy.
# Deliberately not ``reduce_graphql_page_size`` (steps of 5): a query reads up to
# GRAPHQL_PRS_PER_QUERY pull requests' checks at once, so every rejected attempt is
# slow, and stepping down by 5 would burn many of them before finding a size that fits.
# Halving gets there in at most four tries; the transport already shrinks ``first`` on
# gateway timeouts itself. Only a single pull request walks it: a query for several is
# split instead (see ``_query``).
_CONTEXTS_PAGE_SIZE_BACKOFF = (REQUIRED_CHECKS_CONTEXTS_PAGE_SIZE, 50, 25, 10)
# A pull request with more checks than this is reported as unknown rather than read
# without bound.
MAX_CONTEXT_PAGES_PER_PR = 10


# What reading the checks can fail with: GraphQL errors, HTTP errors and rate limits.
# Anything else is a bug and should surface rather than leave the status unknown.
_FETCH_ERRORS = (
    GraphQLErrorGroup,
    GraphQLForbiddenFieldError,
    GraphQLClientError,
    RateLimitException,
    httpx.HTTPError,
)


def _is_too_heavy(error: Exception) -> bool:
    """Whether GitHub rejected the query for its size, so fewer PRs may fit."""
    return isinstance(
        error, GraphQLErrorGroup
    ) or GithubGraphQLClient.is_query_too_expensive(error)


class GraphQLRequiredChecksEnricher:
    """Required checks status from GraphQL, which flags required checks itself.

    Runs separately from the pull request list query so the list query (which already
    sheds fields when GitHub's budget is exceeded) is unaffected. Pull requests are
    read in small aliased batches, following the check contexts cursor of any pull
    request with more checks than a page.

    A query GitHub finds too heavy is retried with smaller pages of checks and then
    with fewer pull requests. Concurrency is bounded by the GraphQL client's own
    limiter, which these queries share with the pull request list queries.
    """

    def __init__(
        self,
        client: GithubGraphQLClient,
        organization: str,
        repo_name: str,
        excluded: Sequence[str],
    ) -> None:
        self._client = client
        self._organization = organization
        self._repo_name = repo_name
        self._excluded = list(excluded)

    async def enrich(self, pull_requests: list[dict[str, Any]]) -> None:
        """Set the required checks fields on each pull request, in place."""
        numbers = [pr["number"] for pr in pull_requests if pr.get("number")]
        if not numbers:
            return

        chunks = [list(chunk) for chunk in batched(numbers, GRAPHQL_PRS_PER_QUERY)]
        summaries: dict[int, Optional[RequiredChecksSummary]] = {}
        for chunk_summaries in await asyncio.gather(
            *(self._summarize_chunk(chunk) for chunk in chunks)
        ):
            summaries.update(chunk_summaries)

        for pull_request in pull_requests:
            number = pull_request.get("number")
            apply_required_checks(
                pull_request, summaries.get(number) if number else None
            )

    async def _summarize_chunk(
        self, numbers: list[int]
    ) -> dict[int, Optional[RequiredChecksSummary]]:
        try:
            checks = await self._fetch_chunk(numbers)
        except _FETCH_ERRORS as error:
            if _is_too_heavy(error) and len(numbers) > 1:
                middle = len(numbers) // 2
                logger.warning(
                    f"[GraphQL] Required checks query for {self._organization}/"
                    f"{self._repo_name}#{numbers} was too heavy; retrying as "
                    f"{middle} and {len(numbers) - middle} pull request(s)"
                )
                halves = await asyncio.gather(
                    self._summarize_chunk(numbers[:middle]),
                    self._summarize_chunk(numbers[middle:]),
                )
                return {**halves[0], **halves[1]}
            logger.warning(
                "[GraphQL] Failed to compute required checks status for "
                f"{self._organization}/{self._repo_name}#{numbers}",
                exc_info=True,
            )
            return {number: None for number in numbers}

        summaries: dict[int, Optional[RequiredChecksSummary]] = {}
        for number in numbers:
            pr_checks = checks.get(number)
            if pr_checks is None or not pr_checks.complete:
                if pr_checks is not None:
                    logger.warning(
                        "[GraphQL] Required checks of "
                        f"{self._organization}/{self._repo_name}#{number} could not be "
                        "read completely; status is unknown"
                    )
                summaries[number] = None
                continue
            summaries[number] = summarize_required_checks(
                expected=pr_checks.expected,
                observed=pr_checks.observed,
                excluded=self._excluded,
                sha=pr_checks.sha,
            )
        return summaries

    async def _fetch_chunk(self, numbers: list[int]) -> dict[int, PullRequestChecks]:
        checks: dict[int, PullRequestChecks] = {}
        cursors: dict[int, Optional[str]] = {number: None for number in numbers}
        pages_read = {number: 0 for number in numbers}

        while cursors:
            repository = await self._query(cursors)
            next_cursors: dict[int, Optional[str]] = {}
            for number, cursor in cursors.items():
                pr_node = repository.get(required_checks_alias(number))
                # Anything but an open PR (it may have closed since it was listed) has
                # no required checks status.
                if not pr_node or pr_node.get("state") != "OPEN":
                    continue

                page = parse_pull_request_node(pr_node)
                pages_read[number] += 1
                pr_checks = checks.get(number)
                if pr_checks is None:
                    pr_checks = checks[number] = page
                else:
                    pr_checks.observed.extend(page.observed)
                    pr_checks.complete = pr_checks.complete and page.complete

                if not page.next_cursor:
                    continue
                if (
                    pages_read[number] >= MAX_CONTEXT_PAGES_PER_PR
                    or page.next_cursor == cursor
                ):
                    logger.warning(
                        f"[GraphQL] Stopped reading the checks of {self._organization}/"
                        f"{self._repo_name}#{number} after {pages_read[number]} page(s)"
                    )
                    pr_checks.complete = False
                else:
                    next_cursors[number] = page.next_cursor
            cursors = next_cursors
        return checks

    async def _query(self, cursors: Mapping[int, Optional[str]]) -> dict[str, Any]:
        """One query. A single pull request is retried with smaller pages of checks when
        GitHub rejects it as too heavy.

        A query for several pull requests is not: it is split by the caller anyway, and
        walking the page sizes at every level of the split multiplies the requests.
        """
        query = generate_pull_requests_required_checks_gql(cursors)
        page_sizes = (
            _CONTEXTS_PAGE_SIZE_BACKOFF
            if len(cursors) == 1
            else (REQUIRED_CHECKS_CONTEXTS_PAGE_SIZE,)
        )
        for page_size in page_sizes[:-1]:
            try:
                return await self._send(query, cursors, page_size)
            except GraphQLErrorGroup:
                logger.warning(
                    f"[GraphQL] Required checks query failed at first={page_size} for "
                    f"{self._organization}/{self._repo_name}#{list(cursors)}"
                )
        return await self._send(query, cursors, page_sizes[-1])

    async def _send(
        self, query: str, cursors: Mapping[int, Optional[str]], page_size: int
    ) -> dict[str, Any]:
        variables = {"organization": self._organization, "repo": self._repo_name}
        payload = self._client.build_graphql_payload(
            query, variables, page_size=page_size
        )
        response = await self._client.send_api_request(
            self._client.base_url,
            method="POST",
            json_data=payload,
            query_path="repository.pullRequest.requiredChecks",
            query_params={**variables, "pullRequests": list(cursors)},
        )
        return ((response.get("data") or {}).get("repository")) or {}
