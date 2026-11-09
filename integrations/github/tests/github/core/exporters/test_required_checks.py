from typing import Any, Optional


import pytest
from github.core.exporters.pull_request_exporter.required_checks import (
    ObservedCheck,
    check_run_outcome,
    status_context_outcome,
    summarize_required_checks,
)

AVIATOR = "aviator/checks"
GATE = "Wait For Required Checks"

EARLIER = "2026-11-08T10:00:00Z"
LATER = "2026-11-08T11:00:00Z"


def _required(
    name: str, outcome: str, started_at: Optional[str] = EARLIER
) -> ObservedCheck:
    return ObservedCheck(name, outcome, True, started_at)  # type: ignore[arg-type]


def _optional(name: str, outcome: str) -> ObservedCheck:
    return ObservedCheck(name, outcome, False, EARLIER)  # type: ignore[arg-type]


def _summarize(
    expected: list[str],
    observed: list[ObservedCheck],
    excluded: Optional[list[str]] = None,
) -> Any:
    return summarize_required_checks(
        expected=expected, observed=observed, excluded=excluded or [], sha="abc"
    )


class TestOutcomes:
    @pytest.mark.parametrize(
        "status, conclusion, expected",
        [
            ("COMPLETED", "SUCCESS", "success"),
            ("COMPLETED", "SKIPPED", "success"),
            ("COMPLETED", "NEUTRAL", "success"),
            ("COMPLETED", "FAILURE", "failure"),
            ("COMPLETED", "TIMED_OUT", "failure"),
            ("COMPLETED", "CANCELLED", "failure"),
            ("COMPLETED", "ACTION_REQUIRED", "failure"),
            ("COMPLETED", "STARTUP_FAILURE", "failure"),
            ("COMPLETED", "STALE", "failure"),
            ("IN_PROGRESS", None, "pending"),
            ("QUEUED", None, "pending"),
            ("WAITING", None, "pending"),
            ("COMPLETED", None, "pending"),
        ],
    )
    def test_check_run_outcome(
        self, status: str, conclusion: Optional[str], expected: str
    ) -> None:
        assert check_run_outcome(status, conclusion) == expected

    @pytest.mark.parametrize(
        "state, expected",
        [
            ("SUCCESS", "success"),
            ("FAILURE", "failure"),
            ("ERROR", "failure"),
            ("PENDING", "pending"),
            ("EXPECTED", "pending"),
            (None, "pending"),
        ],
    )
    def test_status_context_outcome(self, state: Optional[str], expected: str) -> None:
        assert status_context_outcome(state) == expected


class TestSummarizeRequiredChecks:
    def test_excluded_pending_check_does_not_block_success(self) -> None:
        summary = _summarize(
            [GATE, AVIATOR],
            [_required(GATE, "success"), _required(AVIATOR, "pending")],
            excluded=[AVIATOR],
        )

        assert summary.status == "success"
        assert summary.failing == []
        assert summary.pending == []
        assert summary.sha == "abc"

    def test_without_exclusion_the_pending_check_blocks(self) -> None:
        summary = _summarize(
            [GATE, AVIATOR],
            [_required(GATE, "success"), _required(AVIATOR, "pending")],
        )

        assert summary.status == "pending"
        assert summary.pending == [AVIATOR]

    def test_failure_takes_precedence_over_pending(self) -> None:
        summary = _summarize(
            ["lint", "test"],
            [_required("lint", "failure"), _required("test", "pending")],
        )

        assert summary.status == "failure"
        assert summary.failing == ["lint"]
        assert summary.pending == ["test"]

    def test_expected_check_not_reported_yet_is_pending(self) -> None:
        summary = _summarize(["lint", "test"], [_required("lint", "success")])

        assert summary.status == "pending"
        assert summary.pending == ["test"]

    def test_optional_failing_check_is_ignored(self) -> None:
        summary = _summarize(
            ["lint"], [_required("lint", "success"), _optional("wiz", "failure")]
        )

        assert summary.status == "success"
        assert summary.failing == []

    def test_no_required_checks_is_none(self) -> None:
        summary = _summarize([], [_optional("wiz", "failure")])

        assert summary.status == "no_required_checks"

    def test_only_excluded_required_checks_is_no_required_checks(self) -> None:
        summary = _summarize(
            [AVIATOR], [_required(AVIATOR, "pending")], excluded=[AVIATOR]
        )

        assert summary.status == "no_required_checks"

    def test_exclusions_support_glob_patterns(self) -> None:
        summary = _summarize(
            ["aviator/checks", "aviator/other"], [], excluded=["aviator/*"]
        )

        assert summary.status == "no_required_checks"

    def test_latest_run_wins_over_a_superseded_failure(self) -> None:
        summary = _summarize(
            ["build"],
            [
                _required("build", "failure", EARLIER),
                _required("build", "success", LATER),
            ],
        )

        assert summary.status == "success"
        assert summary.failing == []

    def test_latest_run_wins_regardless_of_report_order(self) -> None:
        summary = _summarize(
            ["build"],
            [
                _required("build", "success", LATER),
                _required("build", "failure", EARLIER),
            ],
        )

        assert summary.status == "success"

    def test_newer_failure_supersedes_an_older_success(self) -> None:
        summary = _summarize(
            ["build"],
            [
                _required("build", "success", EARLIER),
                _required("build", "failure", LATER),
            ],
        )

        assert summary.status == "failure"
        assert summary.failing == ["build"]

    def test_run_that_has_not_started_is_the_newest(self) -> None:
        summary = _summarize(
            ["build"],
            [
                _required("build", "failure", EARLIER),
                _required("build", "pending", None),
            ],
        )

        assert summary.status == "pending"
        assert summary.pending == ["build"]

    def test_reports_tied_for_latest_resolve_to_the_worst(self) -> None:
        summary = _summarize(
            ["build"],
            [
                _required("build", "success", LATER),
                _required("build", "failure", LATER),
            ],
        )

        assert summary.status == "failure"


class TestExclusionPatterns:
    @pytest.mark.parametrize(
        "name, pattern, excluded",
        [
            ("aviator/checks", "aviator/checks", True),
            ("aviator/checks", "aviator/*", True),
            ("aviator/checks", "aviator*", True),
            ("aviator/checks", "*checks", True),
            ("aviator/checks", "*", True),
            ("wiz/scan", "@(aviator|wiz)/*", True),
            ("ci/circleci: build", "ci/*", True),
            ("Aviator/Checks", "aviator/*", False),
            ("aviator/checks", "wiz*", False),
        ],
    )
    def test_names_are_matched_as_plain_strings_and_case_sensitively(
        self, name: str, pattern: str, excluded: bool
    ) -> None:
        summary = _summarize([name], [], excluded=[pattern])

        assert (summary.status == "no_required_checks") is excluded
