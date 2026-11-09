"""Status of only the checks GitHub requires for merging a pull request.

GitHub's combined rollup (``statusCheckRollup``) covers every check on the head
commit, so one optional or never-settling check (for example a merge queue check) keeps
it pending forever. This module narrows it down to the required checks, optionally
minus a configurable exclusion list, the way GitHub's own merge gate sees them: a required
check is satisfied by the latest run of that name.

It holds the pure logic: reading a pull request's GraphQL node into
``PullRequestChecks`` (``parse_pull_request_node``) and reducing those to the result
(``summarize_required_checks``). Fetching the data lives in
``required_checks_enricher``.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Optional, Sequence

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
class PullRequestChecks:
    sha: Optional[str]
    expected: list[str]
    observed: list[ObservedCheck]
    next_cursor: Optional[str]
    # False when any part of the data could not be trusted (a check whose
    # isRequired came back null, or checks that could not all be read).
    complete: bool = True


def parse_pull_request_node(pr_node: Mapping[str, Any]) -> PullRequestChecks:
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

    return PullRequestChecks(
        sha=commit.get("oid") or pr_node.get("headRefOid"),
        expected=list(required_contexts),
        observed=observed,
        next_cursor=(
            page_info.get("endCursor") if page_info.get("hasNextPage") else None
        ),
        complete=complete,
    )
