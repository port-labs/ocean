"""Command-line entry for the integration validation runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from tools.integration_validation.runner.results.evaluate import ScenarioComparison
from tools.integration_validation.runner.core.errors import ValidationCliError
from tools.integration_validation.runner.core.statuses import (
    ComparisonStatus,
    ResyncStatus,
    ScenarioIntegrationStatus,
)
from tools.integration_validation.runner.integration.process import (
    DEFAULT_INTEGRATION_TIMEOUT_SECONDS,
    DEFAULT_MOCK_BASE_URL,
)
from tools.integration_validation.runner.runner import (
    ScenarioRun,
    ValidateOptions,
    run_validate,
    write_error_report,
)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate an integration using local fixtures and the developer's Port org."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Integration root (default: current directory).",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenario_names",
        metavar="NAME",
        help="Run only the named scenario(s). May be passed multiple times.",
    )
    parser.add_argument(
        "--update-expected",
        action="store_true",
        help="Write actual Port entities to expected/ when diffs are intended.",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Leave Port resources from the run in place (skip cleanup).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        dest="report_path",
        metavar="PATH",
        help="Write a machine-readable JSON report to this file.",
    )
    parser.add_argument(
        "--mock-base-url",
        dest="mock_base_url",
        default=DEFAULT_MOCK_BASE_URL,
        metavar="URL",
        help=(
            "Base URL of a mock server already running and loaded with the scenario "
            f"(default: {DEFAULT_MOCK_BASE_URL}). Runs `ocean sail -O` after Port "
            "preparation."
        ),
    )
    parser.add_argument(
        "--integration-timeout",
        type=float,
        default=DEFAULT_INTEGRATION_TIMEOUT_SECONDS,
        dest="integration_timeout_seconds",
        metavar="SECONDS",
        help="Max seconds to wait for the integration subprocess (default: 180).",
    )
    args = parser.parse_args(argv)
    options = ValidateOptions(
        integration_path=args.path,
        scenario_names=args.scenario_names,
        update_expected=args.update_expected,
        skip_cleanup=args.skip_cleanup,
        report_path=args.report_path,
        mock_base_url=args.mock_base_url,
        integration_timeout_seconds=args.integration_timeout_seconds,
    )

    try:
        result = run_validate(options)
    except ValidationCliError as error:
        print(f"{error.prefix}: {error.message}", file=sys.stderr)
        write_error_report(options, error)
        raise SystemExit(error.exit_code) from error

    runs = result.scenario_runs
    print(f"{result.paths.integration_name}: {len(runs)} scenario(s)")
    for run in runs:
        _print_scenario(run)

    unverified = sorted(
        {route_id for run in runs for route_id in run.unverified_route_ids}
    )
    if unverified:
        print(f"Unverified routes: {', '.join(unverified)}")
    passed = sum(run.passed for run in runs)
    print(f"{passed} passed, {len(runs) - passed} failed")
    if not result.passed:
        raise SystemExit(1)


def _print_scenario(run: ScenarioRun) -> None:
    entities = sum(len(entities) for entities in run.collection.entities.values())
    unmatched = run.collection.mock.unmatched_requests
    print(
        f"  {'PASS' if run.passed else 'FAIL'}  {run.plan.scenario_name}: "
        f"{entities} entities, {len(unmatched)} unmatched requests, "
        f"expected entities {_comparison_label(run.comparison)}"
    )
    integration_status = run.integration.integration_status()
    if integration_status != ScenarioIntegrationStatus.COMPLETED:
        _print_detail(
            f"{integration_status} (exit {run.integration.returncode}), "
            f"see the report's integration logs"
        )
    if run.collection.resync_status != ResyncStatus.COMPLETED:
        _print_detail(f"resync status in Port: {run.collection.resync_status}")
    for entry in unmatched:
        _print_detail(f"unmatched: {entry.method} {entry.path}")
    _print_entity_diff(run.comparison)
    if run.cleanup_leftovers:
        _print_detail(f"cleanup left behind: {', '.join(run.cleanup_leftovers)}")
    elif not run.cleaned_up:
        _print_detail(
            f"kept in Port: {run.plan.integration_identifier}, "
            f"{', '.join(run.plan.blueprint_renames.values())}"
        )


def _print_entity_diff(comparison: ScenarioComparison) -> None:
    for blueprint, diff in comparison.entity_diff.items():
        for identifier in diff.added:
            _print_detail(f"{blueprint} + {identifier} (unexpected)")
        for identifier in diff.removed:
            _print_detail(f"{blueprint} - {identifier} (missing)")
        for change in diff.changed:
            _print_detail(
                f"{blueprint} {change.identifier} {change.field}: "
                f"{json.dumps(change.expected)} -> {json.dumps(change.actual)}"
            )


def _print_detail(message: str) -> None:
    print(f"        {message}", file=sys.stderr)


COMPARISON_LABELS: dict[ComparisonStatus, str] = {
    ComparisonStatus.MATCHED: "matched",
    ComparisonStatus.DIFFERENT: "{differences} difference(s) from {location}",
}


def _comparison_label(comparison: ScenarioComparison) -> str:
    return COMPARISON_LABELS[comparison.status].format(
        differences=comparison.difference_count,
        location=comparison.expected_dir,
    )
