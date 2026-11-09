"""Status of only the checks GitHub requires for merging a pull request.

GitHub's combined rollup (``statusCheckRollup``) covers every check on the head
commit, so one optional or never-settling check (for example a merge queue check) keeps
it pending forever. This module narrows it down to the required checks, optionally
minus a configurable exclusion list, the way GitHub's own merge gate sees them: a required
check is satisfied by the latest run of that name.

GraphQL flags required checks itself (``isRequired``), so ``GraphQLRequiredChecksEnricher``
only has to read the head commit's check contexts. ``summarize_required_checks`` turns
them into the result.
"""

import asyncio
from dataclasses import dataclass
from itertools import batched
from typing import Any, Iterable, Literal, Mapping, Optional, Sequence

import httpx
from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
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
from github.helpers.utils import matches_glob_pattern

CheckOutcome = Literal["success", "failure", "pending"]
# "no_required_checks" means no check is required (nothing blocks the PR on checks),
# while "unknown" means the status could not be determined.
RequiredChecksStatus = Literal[
    "success", "failure", "pending", "no_required_checks", "unknown"
]

REQUIRED_CHECKS_STATUS_FIELD = "required_checks_status"
REQUIRED_CHECKS_FAILING_FIELD = "required_checks_failing"
REQUIRED_CHECKS_PENDING_FIELD = "required_checks_pending"
REQUIRED_CHECKS_SHA_FIELD = "required_checks_sha"

# GitHub treats these conclusions of a required check as passing.
_PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
_FAILING_STATUS_STATES = frozenset({"FAILURE", "ERROR"})

GRAPHQL_PRS_PER_QUERY = 5
# Page sizes of the check contexts to try when GitHub rejects the query as too heavy.
# Deliberately not ``reduce_graphql_page_size`` (steps of 5): a query reads up to
# GRAPHQL_PRS_PER_QUERY pull requests' checks at once, so every rejected attempt is
# slow, and stepping down by 5 would burn many of them before finding a size that fits.
# Halving gets there in at most four tries; the transport already shrinks ``first`` on
# gateway timeouts itself.
_CONTEXTS_PAGE_SIZE_BACKOFF = (REQUIRED_CHECKS_CONTEXTS_PAGE_SIZE, 50, 25, 10)
# A pull request with more checks than this is reported as unknown rather than read
# without bound.
MAX_CONTEXT_PAGES_PER_PR = 10


@dataclass(frozen=True)
class ObservedCheck:
    """A check reported on the head commit.

    ``started_at`` is when the check run started (or the status was created). ``None``
    means it has not started yet, which makes it the newest report of its name.
    """

    name: str
    outcome: CheckOutcome
    is_required: bool
    started_at: Optional[str] = None


@dataclass(frozen=True)
class RequiredChecksSummary:
    status: RequiredChecksStatus
    failing: list[str]
    pending: list[str]
    sha: Optional[str]


def check_run_outcome(status: Optional[str], conclusion: Optional[str]) -> CheckOutcome:
    """Outcome of a GraphQL check run (``status`` and ``conclusion`` are uppercase enums)."""
    if status != "COMPLETED" or not conclusion:
        return "pending"
    return "success" if conclusion in _PASSING_CONCLUSIONS else "failure"


def status_context_outcome(state: Optional[str]) -> CheckOutcome:
    """Outcome of a GraphQL commit status (``state`` is an uppercase enum)."""
    if state == "SUCCESS":
        return "success"
    if state in _FAILING_STATUS_STATES:
        return "failure"
    return "pending"


def _is_excluded(name: str, excluded: Iterable[str]) -> bool:
    return any(matches_glob_pattern(name, pattern) for pattern in excluded)


def _latest_outcome(observations: Sequence[ObservedCheck]) -> CheckOutcome:
    """Outcome of the most recent report of a check, like GitHub's merge gate.

    A re-run as a new check suite leaves the superseded run in the rollup, so folding
    every report of a name would let an old failure outlive the re-run that fixed it.
    Reports tied for the latest (e.g. two that have not started) resolve to the worst.
    """
    latest = max((o.started_at is None, o.started_at or "") for o in observations)
    outcomes = {
        o.outcome
        for o in observations
        if (o.started_at is None, o.started_at or "") == latest
    }
    if "failure" in outcomes:
        return "failure"
    return "pending" if "pending" in outcomes else "success"


def summarize_required_checks(
    *,
    expected: Sequence[str],
    observed: Sequence[ObservedCheck],
    excluded: Sequence[str],
    sha: Optional[str],
) -> RequiredChecksSummary:
    """Reduce the required check names and the reported checks to the status.

    * ``failure``: a required check failed (takes precedence over pending, so a
      consumer can react as soon as one fails).
    * ``pending``: a required check is still running, or has not been reported yet.
    * ``success``: every required check passed or was skipped.
    * ``no_required_checks``: no required check applies once ``excluded`` is applied.
    """
    reports_by_name: dict[str, list[ObservedCheck]] = {}

    # An expected check with no report yet stays an empty list, i.e. pending.
    for name in expected:
        if not _is_excluded(name, excluded):
            reports_by_name.setdefault(name, [])

    for observed_check in observed:
        if observed_check.is_required and not _is_excluded(
            observed_check.name, excluded
        ):
            reports_by_name.setdefault(observed_check.name, []).append(observed_check)

    failing: list[str] = []
    pending: list[str] = []
    for name, reports in sorted(reports_by_name.items()):
        outcome = _latest_outcome(reports) if reports else "pending"
        if outcome == "failure":
            failing.append(name)
        elif outcome == "pending":
            pending.append(name)

    status: RequiredChecksStatus
    if not reports_by_name:
        status = "no_required_checks"
    elif failing:
        status = "failure"
    elif pending:
        status = "pending"
    else:
        status = "success"
    return RequiredChecksSummary(
        status=status, failing=failing, pending=pending, sha=sha
    )


def apply_required_checks(
    pull_request: dict[str, Any], summary: Optional[RequiredChecksSummary]
) -> None:
    """Write the summary onto the raw PR; ``None`` (unknown) sets the status to
    ``unknown`` and leaves the other fields null."""
    pull_request[REQUIRED_CHECKS_STATUS_FIELD] = (
        summary.status if summary else "unknown"
    )
    pull_request[REQUIRED_CHECKS_FAILING_FIELD] = summary.failing if summary else None
    pull_request[REQUIRED_CHECKS_PENDING_FIELD] = summary.pending if summary else None
    pull_request[REQUIRED_CHECKS_SHA_FIELD] = summary.sha if summary else None


@dataclass
class _GraphQLPullRequestChecks:
    sha: Optional[str]
    expected: list[str]
    observed: list[ObservedCheck]
    next_cursor: Optional[str]
    # False when any part of the data could not be trusted (a check whose
    # isRequired came back null, or checks that could not all be read).
    complete: bool = True


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
    ) or GithubGraphQLClient._is_query_too_expensive(error)


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

    async def _fetch_chunk(
        self, numbers: list[int]
    ) -> dict[int, _GraphQLPullRequestChecks]:
        checks: dict[int, _GraphQLPullRequestChecks] = {}
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

                page = _parse_pull_request_node(pr_node)
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
        """One query, with smaller pages of checks when GitHub rejects it as too heavy."""
        query = generate_pull_requests_required_checks_gql(cursors)
        last_error: Optional[GraphQLErrorGroup] = None
        for page_size in _CONTEXTS_PAGE_SIZE_BACKOFF:
            variables = {"organization": self._organization, "repo": self._repo_name}
            payload = self._client.build_graphql_payload(
                query, variables, page_size=page_size
            )
            try:
                response = await self._client.send_api_request(
                    self._client.base_url,
                    method="POST",
                    json_data=payload,
                    query_path="repository.pullRequest.requiredChecks",
                    query_params={**variables, "pullRequests": list(cursors)},
                )
            except GraphQLErrorGroup as error:
                last_error = error
                logger.warning(
                    f"[GraphQL] Required checks query failed at first={page_size} for "
                    f"{self._organization}/{self._repo_name}#{list(cursors)}"
                )
                continue
            return ((response.get("data") or {}).get("repository")) or {}
        assert last_error is not None
        raise last_error


def _parse_pull_request_node(pr_node: Mapping[str, Any]) -> _GraphQLPullRequestChecks:
    commit_nodes = (pr_node.get("commits") or {}).get("nodes") or []
    commit = (commit_nodes[0] if commit_nodes else {}).get("commit") or {}
    contexts = ((commit.get("statusCheckRollup") or {}).get("contexts")) or {}
    page_info = contexts.get("pageInfo") or {}

    required_contexts = ((pr_node.get("baseRef") or {}).get("refUpdateRule") or {}).get(
        "requiredStatusCheckContexts"
    ) or []

    observed: list[ObservedCheck] = []
    complete = True
    for node in contexts.get("nodes") or []:
        if not node:
            continue
        if node.get("__typename") == "CheckRun":
            name = node.get("name")
            outcome = check_run_outcome(node.get("status"), node.get("conclusion"))
            started_at = node.get("startedAt")
        else:
            name = node.get("context")
            outcome = status_context_outcome(node.get("state"))
            started_at = node.get("createdAt")
        if not name:
            continue
        is_required = node.get("isRequired")
        if is_required is None:
            # Treating it as optional could drop a required check that passed, and
            # treating it as required could block on an optional one: give up instead.
            complete = False
            continue
        observed.append(
            ObservedCheck(
                name=name,
                outcome=outcome,
                is_required=is_required,
                started_at=started_at,
            )
        )

    return _GraphQLPullRequestChecks(
        sha=commit.get("oid") or pr_node.get("headRefOid"),
        expected=list(required_contexts),
        observed=observed,
        next_cursor=(
            page_info.get("endCursor") if page_info.get("hasNextPage") else None
        ),
        complete=complete,
    )
