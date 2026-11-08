"""Status of only the checks GitHub requires for merging a pull request.

GitHub's combined rollup (``statusCheckRollup`` / the commit status API) covers every
check on the head commit, so one optional or never-settling check (for example a merge
queue check) keeps it pending forever. This module narrows it down to the required
checks, optionally minus a configurable ignore list.

The result is computed by the transport-agnostic ``summarize_required_checks`` from two
inputs:

* the checks that are *expected* (required by branch protection / rulesets), and
* the checks *observed* on the head commit.

Only GraphQL feeds it today (``GraphQLRequiredChecksEnricher``): its ``isRequired`` flag
makes this cheap. A REST enricher would build the same two inputs from the branch
protection, rulesets, check runs and commit statuses endpoints.
"""

import asyncio
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Iterable, Literal, Mapping, Optional, Sequence

from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.helpers.gql_queries import (
    generate_pull_requests_required_checks_gql,
    required_checks_alias,
)

CheckOutcome = Literal["success", "failure", "pending"]
RequiredChecksStatus = Literal["success", "failure", "pending", "none"]

REQUIRED_CHECKS_STATUS_FIELD = "required_checks_status"
REQUIRED_CHECKS_FAILING_FIELD = "required_checks_failing"
REQUIRED_CHECKS_PENDING_FIELD = "required_checks_pending"
REQUIRED_CHECKS_SHA_FIELD = "required_checks_sha"

# GitHub treats these conclusions of a required check as passing.
_PASSING_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
_FAILING_STATUS_STATES = frozenset({"failure", "error"})
_PASSING_STATUS_STATES = frozenset({"success"})

GRAPHQL_PRS_PER_QUERY = 5
GRAPHQL_CONCURRENT_QUERIES = 3


@dataclass(frozen=True)
class ExpectedCheck:
    """A check that branch protection or a ruleset requires."""

    name: str
    app_id: Optional[int] = None

    def is_satisfied_by_source(self, observed: "ObservedCheck") -> bool:
        # A missing or non-positive app id means "any app" in GitHub's settings.
        if not self.app_id or self.app_id < 0 or observed.app_id is None:
            return True
        return self.app_id == observed.app_id


@dataclass(frozen=True)
class ObservedCheck:
    """A check reported on the head commit.

    ``is_required`` is set when the API says so itself (GraphQL ``isRequired``); when
    ``None`` it is decided by matching against the expected checks.
    """

    name: str
    outcome: CheckOutcome
    app_id: Optional[int] = None
    is_required: Optional[bool] = None


@dataclass(frozen=True)
class RequiredChecksSummary:
    status: RequiredChecksStatus
    failing: list[str]
    pending: list[str]
    sha: Optional[str]


def check_run_outcome(status: Optional[str], conclusion: Optional[str]) -> CheckOutcome:
    """Outcome of a check run, from either API (REST is lowercase, GraphQL uppercase)."""
    if (status or "").lower() != "completed":
        return "pending"
    normalized = (conclusion or "").lower()
    if not normalized:
        return "pending"
    return "success" if normalized in _PASSING_CONCLUSIONS else "failure"


def status_context_outcome(state: Optional[str]) -> CheckOutcome:
    """Outcome of a commit status, from either API."""
    normalized = (state or "").lower()
    if normalized in _PASSING_STATUS_STATES:
        return "success"
    if normalized in _FAILING_STATUS_STATES:
        return "failure"
    return "pending"


def _is_ignored(name: str, ignore: Iterable[str]) -> bool:
    return any(fnmatchcase(name, pattern) for pattern in ignore)


def summarize_required_checks(
    *,
    expected: Sequence[ExpectedCheck],
    observed: Sequence[ObservedCheck],
    ignore: Sequence[str],
    sha: Optional[str],
) -> RequiredChecksSummary:
    """Reduce expected and observed checks to the required checks status.

    * ``failure``: a required check failed (takes precedence over pending, so a
      consumer can react as soon as one fails).
    * ``pending``: a required check is still running, or has not been reported yet.
    * ``success``: every required check passed or was skipped.
    * ``none``: no required check applies once ``ignore`` is applied.
    """
    outcomes_by_name: dict[str, list[CheckOutcome]] = {}

    # An expected check with no report yet stays an empty list, i.e. pending.
    for expected_check in expected:
        if not _is_ignored(expected_check.name, ignore):
            outcomes_by_name.setdefault(expected_check.name, [])

    for observed_check in observed:
        if _is_ignored(observed_check.name, ignore):
            continue
        is_required = observed_check.is_required
        if is_required is None:
            is_required = any(
                expected_check.name == observed_check.name
                and expected_check.is_satisfied_by_source(observed_check)
                for expected_check in expected
            )
        if is_required:
            outcomes_by_name.setdefault(observed_check.name, []).append(
                observed_check.outcome
            )

    failing: list[str] = []
    pending: list[str] = []
    for name, outcomes in sorted(outcomes_by_name.items()):
        if "failure" in outcomes:
            failing.append(name)
        elif not outcomes or "pending" in outcomes:
            pending.append(name)

    status: RequiredChecksStatus
    if not outcomes_by_name:
        status = "none"
    elif failing:
        status = "failure"
    elif pending:
        status = "pending"
    else:
        status = "success"
    return RequiredChecksSummary(
        status=status, failing=failing, pending=pending, sha=sha
    )


def pop_required_checks_options(options: dict[str, Any]) -> tuple[bool, list[str]]:
    """Take the required checks options out of exporter options.

    Returns ``(include_required_checks_status, required_checks_ignore)``.
    """
    include = bool(options.pop("include_required_checks_status", False))
    ignore = list(options.pop("required_checks_ignore", None) or [])
    return include, ignore


def apply_required_checks(
    pull_request: dict[str, Any], summary: Optional[RequiredChecksSummary]
) -> dict[str, Any]:
    """Write the summary onto the raw PR; ``None`` (unknown) leaves every field null."""
    pull_request[REQUIRED_CHECKS_STATUS_FIELD] = summary.status if summary else None
    pull_request[REQUIRED_CHECKS_FAILING_FIELD] = summary.failing if summary else None
    pull_request[REQUIRED_CHECKS_PENDING_FIELD] = summary.pending if summary else None
    pull_request[REQUIRED_CHECKS_SHA_FIELD] = summary.sha if summary else None
    return pull_request


@dataclass
class _GraphQLPullRequestChecks:
    sha: Optional[str]
    expected: list[ExpectedCheck]
    observed: list[ObservedCheck]
    next_cursor: Optional[str]


class GraphQLRequiredChecksEnricher:
    """Required checks status from GraphQL, which flags required checks itself.

    Runs separately from the pull request list query so the list query (which already
    sheds fields when GitHub's budget is exceeded) is unaffected. Pull requests are
    read in small aliased batches, following the check contexts cursor of any pull
    request with more checks than a page.
    """

    def __init__(
        self,
        client: GithubGraphQLClient,
        organization: str,
        repo_name: str,
        ignore: Sequence[str],
    ) -> None:
        self._client = client
        self._organization = organization
        self._repo_name = repo_name
        self._ignore = list(ignore)
        self._semaphore = asyncio.Semaphore(GRAPHQL_CONCURRENT_QUERIES)

    async def enrich(self, pull_requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        numbers = [pr["number"] for pr in pull_requests if pr.get("number")]
        if not numbers:
            return pull_requests

        chunks = [
            numbers[start : start + GRAPHQL_PRS_PER_QUERY]
            for start in range(0, len(numbers), GRAPHQL_PRS_PER_QUERY)
        ]
        chunk_results = await asyncio.gather(
            *(self._summarize_chunk(chunk) for chunk in chunks)
        )
        summaries: dict[int, Optional[RequiredChecksSummary]] = {}
        for result in chunk_results:
            summaries.update(result)

        for pull_request in pull_requests:
            number = pull_request.get("number")
            apply_required_checks(
                pull_request, summaries.get(number) if number else None
            )
        return pull_requests

    async def _summarize_chunk(
        self, numbers: list[int]
    ) -> dict[int, Optional[RequiredChecksSummary]]:
        async with self._semaphore:
            try:
                checks = await self._fetch_chunk(numbers)
            except Exception:
                logger.warning(
                    "[GraphQL] Failed to compute required checks status for "
                    f"{self._organization}/{self._repo_name}#{numbers}",
                    exc_info=True,
                )
                return {number: None for number in numbers}

        return {
            number: (
                summarize_required_checks(
                    expected=pr_checks.expected,
                    observed=pr_checks.observed,
                    ignore=self._ignore,
                    sha=pr_checks.sha,
                )
                if (pr_checks := checks.get(number)) is not None
                else None
            )
            for number in numbers
        }

    async def _fetch_chunk(
        self, numbers: list[int]
    ) -> dict[int, _GraphQLPullRequestChecks]:
        checks: dict[int, _GraphQLPullRequestChecks] = {}
        cursors: dict[int, Optional[str]] = {number: None for number in numbers}

        while cursors:
            repository = await self._query(cursors)
            next_cursors: dict[int, Optional[str]] = {}
            for number in cursors:
                pr_node = repository.get(required_checks_alias(number))
                if not pr_node:
                    continue
                page = _parse_pull_request_node(pr_node)
                if number in checks:
                    checks[number].observed.extend(page.observed)
                    checks[number].next_cursor = page.next_cursor
                else:
                    checks[number] = page
                if page.next_cursor:
                    next_cursors[number] = page.next_cursor
            cursors = next_cursors
        return checks

    async def _query(self, cursors: Mapping[int, Optional[str]]) -> dict[str, Any]:
        payload = self._client.build_graphql_payload(
            generate_pull_requests_required_checks_gql(cursors),
            {"organization": self._organization, "repo": self._repo_name},
        )
        response = await self._client.send_api_request(
            self._client.base_url, method="POST", json_data=payload
        )
        return ((response.get("data") or {}).get("repository")) or {}


def _parse_pull_request_node(pr_node: Mapping[str, Any]) -> _GraphQLPullRequestChecks:
    commit_nodes = (pr_node.get("commits") or {}).get("nodes") or []
    commit = (commit_nodes[0] if commit_nodes else {}).get("commit") or {}
    contexts = ((commit.get("statusCheckRollup") or {}).get("contexts")) or {}
    page_info = contexts.get("pageInfo") or {}

    required_contexts = ((pr_node.get("baseRef") or {}).get("refUpdateRule") or {}).get(
        "requiredStatusCheckContexts"
    ) or []

    observed: list[ObservedCheck] = []
    for node in contexts.get("nodes") or []:
        if not node:
            continue
        if node.get("__typename") == "CheckRun":
            name = node.get("name")
            outcome = check_run_outcome(node.get("status"), node.get("conclusion"))
        else:
            name = node.get("context")
            outcome = status_context_outcome(node.get("state"))
        if name:
            observed.append(
                ObservedCheck(
                    name=name, outcome=outcome, is_required=bool(node.get("isRequired"))
                )
            )

    return _GraphQLPullRequestChecks(
        sha=commit.get("oid") or pr_node.get("headRefOid"),
        expected=[ExpectedCheck(name=context) for context in required_contexts],
        observed=observed,
        next_cursor=(
            page_info.get("endCursor") if page_info.get("hasNextPage") else None
        ),
    )
