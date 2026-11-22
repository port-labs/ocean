"""Command-line entry for the integration validation runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from tools.integration_validation.runner.errors import ValidationCliError
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
    args = parser.parse_args(argv)

    try:
        result = run_validate(
            ValidateOptions(
                integration_path=args.path,
                scenario_names=args.scenario_names,
                update_expected=args.update_expected,
                skip_cleanup=args.skip_cleanup,
                report_path=args.report_path,
            )
        )
    except ValidationCliError as error:
        print(f"{error.prefix}: {error.message}", file=sys.stderr)
        raise SystemExit(error.exit_code) from error

    integration_name = result.paths.integration_name
    print(f"Loaded {len(result.scenario_names)} scenario(s) for {integration_name}.")
    for name in result.scenario_names:
        kinds = result.scenarios.scenarios[name].kinds
        kinds_label = ", ".join(kinds) if kinds else "all configured kinds"
        print(f"  • {name} ({kinds_label})")

    print(
        "Scenario execution is not implemented yet; preflight checks passed.",
        file=sys.stderr,
    )
