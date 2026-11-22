from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.loader import (
    load_scenarios_document,
    resolve_validation_paths,
)
from tools.integration_validation.runner.models import (
    ScenariosDocument,
    ValidationPaths,
)
from tools.integration_validation.runner.preflight import run_preflight


@dataclass(frozen=True)
class ValidateOptions:
    integration_path: Path
    scenario_names: list[str] | None
    update_expected: bool
    keep: bool
    report_path: Path | None


@dataclass(frozen=True)
class ValidateResult:
    paths: ValidationPaths
    scenarios: ScenariosDocument
    scenario_names: list[str]
    update_expected: bool
    keep: bool
    report_path: Path | None


def run_validate(options: ValidateOptions) -> ValidateResult:
    paths = resolve_validation_paths(options.integration_path)
    scenarios = load_scenarios_document(paths.scenarios_file)
    run_preflight(paths, scenarios, options.scenario_names)

    # TODO(follow-up PRs): run each scenario (Port prep, mock, sail, collect, diff, cleanup).
    if options.scenario_names:
        scenario_names = options.scenario_names
    else:
        scenario_names = list(scenarios.scenarios.keys())

    result = ValidateResult(
        paths=paths,
        scenarios=scenarios,
        scenario_names=scenario_names,
        update_expected=options.update_expected,
        keep=options.keep,
        report_path=options.report_path,
    )

    if options.report_path is not None:
        _write_preflight_report(result)

    return result


def _write_preflight_report(result: ValidateResult) -> None:
    # Placeholder report until full report.json schema is implemented.
    payload = {
        "integration": result.paths.integration_name,
        "status": "preflight_passed",
        "scenarios": [
            {
                "name": name,
                "status": "not_run",
                "kinds": result.scenarios.scenarios[name].kinds,
            }
            for name in result.scenario_names
        ],
        "options": {
            "update_expected": result.update_expected,
            "keep": result.keep,
        },
    }
    report_path = result.report_path
    if report_path is None:
        return
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ValidationSetupError(
            f"Could not write report to {report_path}: {exc}"
        ) from exc
