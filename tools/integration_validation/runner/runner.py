from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from tools.integration_validation.runner.blueprint_rewrite import (
    rewrite_mapping_blueprints,
    suffix_blueprints,
)
from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.loader import (
    load_blueprints_file,
    load_port_app_config_file,
    load_scenarios_document,
    resolve_integration_resource_path,
    resolve_scenario_blueprints_path,
    resolve_validation_paths,
)
from tools.integration_validation.runner.models import (
    ScenariosDocument,
    ValidationPaths,
)
from tools.integration_validation.runner.naming import build_integration_identifier
from tools.integration_validation.runner.port_app_config import (
    build_scenario_port_app_config,
)
from tools.integration_validation.runner.port_setup import (
    ScenarioPortPlan,
    create_port_client,
    prepare_scenario_port,
    teardown_scenario_port,
)
from tools.integration_validation.runner.preflight import (
    load_integration_type,
    run_preflight,
    select_scenario_names,
)


@dataclass(frozen=True)
class ValidateOptions:
    integration_path: Path
    scenario_names: list[str] | None
    update_expected: bool
    skip_cleanup: bool
    report_path: Path | None


@dataclass(frozen=True)
class ScenarioRun:
    plan: ScenarioPortPlan
    cleanup_leftovers: list[str]
    cleaned_up: bool


@dataclass(frozen=True)
class ValidateResult:
    paths: ValidationPaths
    options: ValidateOptions
    scenario_runs: list[ScenarioRun]


def run_validate(options: ValidateOptions) -> ValidateResult:
    paths = resolve_validation_paths(options.integration_path)
    scenarios = load_scenarios_document(paths.scenarios_file)
    run_preflight(paths)

    scenario_names = select_scenario_names(scenarios, options.scenario_names)
    integration_type = load_integration_type()
    plans = _plan_scenarios(paths, scenarios, scenario_names)

    # TODO(follow-up PRs): start the mock and `ocean sail` between prepare and
    # teardown, then collect, diff and report.
    scenario_runs = asyncio.run(
        _run_scenarios(plans, integration_type, options.skip_cleanup)
    )

    result = ValidateResult(paths=paths, options=options, scenario_runs=scenario_runs)
    if options.report_path is not None:
        _write_report(result, options.report_path)
    return result


def _plan_scenarios(
    paths: ValidationPaths,
    scenarios: ScenariosDocument,
    scenario_names: list[str],
) -> list[ScenarioPortPlan]:
    base_config = load_port_app_config_file(
        resolve_integration_resource_path(
            paths, scenarios.defaults.port_app_config, "port_app_config"
        )
    )
    plans: list[ScenarioPortPlan] = []
    for name in scenario_names:
        scenario = scenarios.scenarios[name]
        blueprints = load_blueprints_file(
            resolve_scenario_blueprints_path(paths, scenarios.defaults, scenario)
        )
        suffixed_blueprints, renames = suffix_blueprints(blueprints, name)
        port_app_config = rewrite_mapping_blueprints(
            build_scenario_port_app_config(base_config, name, scenario), renames
        )
        plans.append(
            ScenarioPortPlan(
                scenario_name=name,
                integration_identifier=build_integration_identifier(
                    paths.integration_name, name
                ),
                blueprints=suffixed_blueprints,
                blueprint_renames=renames,
                kinds=scenario.kinds,
                port_app_config=port_app_config,
            )
        )
    return plans


async def _run_scenarios(
    plans: list[ScenarioPortPlan],
    integration_type: str,
    skip_cleanup: bool,
) -> list[ScenarioRun]:
    runs: list[ScenarioRun] = []
    for plan in plans:
        client = create_port_client(plan.integration_identifier, integration_type)
        logger.info(
            f"Preparing Port for scenario '{plan.scenario_name}' "
            f"(integration {plan.integration_identifier})"
        )
        await prepare_scenario_port(client, plan)

        leftovers: list[str] = []
        if not skip_cleanup:
            leftovers = await teardown_scenario_port(client, plan)
        runs.append(
            ScenarioRun(
                plan=plan,
                cleanup_leftovers=leftovers,
                cleaned_up=not skip_cleanup and not leftovers,
            )
        )
    return runs


def _write_report(result: ValidateResult, report_path: Path) -> None:
    # Placeholder report until full report.json schema is implemented.
    payload = {
        "integration": result.paths.integration_name,
        "status": "port_prepared",
        "scenarios": [_scenario_report(run) for run in result.scenario_runs],
        "options": {
            "update_expected": result.options.update_expected,
            "skip_cleanup": result.options.skip_cleanup,
        },
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ValidationSetupError(
            f"Could not write report to {report_path}: {exc}"
        ) from exc


def _scenario_report(run: ScenarioRun) -> dict[str, Any]:
    return {
        "name": run.plan.scenario_name,
        "status": "not_run",
        "kinds": run.plan.kinds,
        "port": {
            "integration_identifier": run.plan.integration_identifier,
            "blueprints": run.plan.blueprint_renames,
            "cleaned_up": run.cleaned_up,
            "cleanup_leftovers": run.cleanup_leftovers,
        },
    }
