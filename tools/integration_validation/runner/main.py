"""Command-line entry for the integration validation runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from tools.integration_validation.runner.collect import ScenarioCollection
from tools.integration_validation.runner.errors import ValidationCliError
from tools.integration_validation.runner.integration_process import (
    DEFAULT_INTEGRATION_TIMEOUT_SECONDS,
    DEFAULT_MOCK_BASE_URL,
)
from tools.integration_validation.runner.runner import ValidateOptions, run_validate


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

    try:
        result = run_validate(
            ValidateOptions(
                integration_path=args.path,
                scenario_names=args.scenario_names,
                update_expected=args.update_expected,
                skip_cleanup=args.skip_cleanup,
                report_path=args.report_path,
                mock_base_url=args.mock_base_url,
                integration_timeout_seconds=args.integration_timeout_seconds,
            )
        )
    except ValidationCliError as error:
        print(f"{error.prefix}: {error.message}", file=sys.stderr)
        raise SystemExit(error.exit_code) from error

    integration_name = result.paths.integration_name
    print(f"Loaded {len(result.scenario_runs)} scenario(s) for {integration_name}.")
    for run in result.scenario_runs:
        name = run.plan.scenario_name
        kinds = run.plan.kinds
        kinds_label = ", ".join(kinds) if kinds else "all configured kinds"
        print(f"  • {name} ({kinds_label})")
        print(f"    integration: {run.plan.integration_identifier}")
        print(f"    blueprints: {', '.join(run.plan.blueprint_renames.values())}")
        if run.integration.timed_out:
            print("    Integration subprocess timed out", file=sys.stderr)
        elif run.integration.returncode != 0:
            print(
                f"    Integration subprocess failed (exit {run.integration.returncode})",
                file=sys.stderr,
            )
        else:
            print("    Integration subprocess completed")
        _print_collection(run.collection)
        if run.cleaned_up:
            print("    Port resources cleaned up")
        elif run.cleanup_leftovers:
            print(
                f"    Cleanup left behind: {', '.join(run.cleanup_leftovers)}",
                file=sys.stderr,
            )
        else:
            print("    Port resources kept (--skip-cleanup)")

    if result.scenario_runs and all(
        not run.integration.timed_out and run.integration.returncode == 0
        for run in result.scenario_runs
    ):
        print("All scenarios completed integration subprocess.", file=sys.stderr)
    else:
        raise SystemExit(1)


def _print_collection(collection: ScenarioCollection) -> None:
    print(f"    Resync status in Port: {collection.resync_status}")
    counts = ", ".join(
        f"{blueprint}={len(entities)}"
        for blueprint, entities in collection.entities.items()
    )
    print(f"    Entities: {counts or 'none'}")
    mock = collection.mock
    unmatched = mock.unmatched_requests
    print(
        f"    Mock requests: {len(mock.requests)} ({len(unmatched)} unmatched, "
        f"{len(mock.unused_route_ids)} unused routes)"
    )
    for entry in unmatched:
        print(f"      unmatched: {entry.method} {entry.path}", file=sys.stderr)
