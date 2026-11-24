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
    ValidationPortClient,
    create_port_client,
    prepare_scenario_port,
    teardown_scenario_port,
)
from tools.integration_validation.runner.integration_config_env import (
    merge_scenario_integration_config,
)
from tools.integration_validation.runner.integration_process import (
    IntegrationRunResult,
    run_ocean_sail_once,
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
    mock_base_url: str
    integration_timeout_seconds: float


@dataclass(frozen=True)
class ScenarioRun:
    plan: ScenarioPortPlan
    cleanup_leftovers: list[str]
    cleaned_up: bool
    integration: IntegrationRunResult


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

    scenario_runs = asyncio.run(
        _run_scenarios(
            paths,
            scenarios,
            plans,
            integration_type,
            options,
        )
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
        ).as_mappings()
        suffixed_blueprints, renames = suffix_blueprints(blueprints, name)
        port_app_config = rewrite_mapping_blueprints(
            build_scenario_port_app_config(base_config, name, scenario),
            renames,
        ).as_mapping()
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
    paths: ValidationPaths,
    scenarios: ScenariosDocument,
    plans: list[ScenarioPortPlan],
    integration_type: str,
    options: ValidateOptions,
) -> list[ScenarioRun]:
    runs: list[ScenarioRun] = []
    for plan in plans:
        runs.append(
            await _run_scenario(
                paths,
                scenarios,
                plan,
                integration_type,
                options,
            )
        )
    return runs


async def _run_scenario(
    paths: ValidationPaths,
    scenarios: ScenariosDocument,
    plan: ScenarioPortPlan,
    integration_type: str,
    options: ValidateOptions,
) -> ScenarioRun:
    client = create_port_client(plan.integration_identifier, integration_type)
    logger.info(
        f"Preparing Port for scenario '{plan.scenario_name}' "
        f"(integration {plan.integration_identifier})"
    )

    leftovers: list[str] = []
    prepared = False

    try:
        await prepare_scenario_port(client, plan)
        prepared = True

        scenario = scenarios.scenarios[plan.scenario_name]
        integration_config = merge_scenario_integration_config(
            scenarios.defaults.integration_config,
            scenario.integration_config,
        )
        integration_result = run_ocean_sail_once(
            paths.integration_root,
            integration_identifier=plan.integration_identifier,
            integration_config=integration_config,
            mock_base_url=options.mock_base_url,
            timeout_seconds=options.integration_timeout_seconds,
        )
    finally:
        if prepared:
            leftovers = await _teardown_scenario(client, plan, options)

    return ScenarioRun(
        plan=plan,
        cleanup_leftovers=leftovers,
        cleaned_up=prepared and not options.skip_cleanup and not leftovers,
        integration=integration_result,
    )


async def _teardown_scenario(
    client: ValidationPortClient,
    plan: ScenarioPortPlan,
    options: ValidateOptions,
) -> list[str]:
    if options.skip_cleanup:
        return []
    leftovers = await teardown_scenario_port(client, plan)
    if leftovers:
        logger.warning(
            f"Scenario '{plan.scenario_name}' cleanup left behind: "
            f"{', '.join(leftovers)}"
        )
    return leftovers


def _write_report(result: ValidateResult, report_path: Path) -> None:
    # Placeholder report until full report.json schema is implemented.
    payload = {
        "integration": result.paths.integration_name,
        "status": _aggregate_status(result),
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
        "status": _scenario_status(run),
        "kinds": run.plan.kinds,
        "port": {
            "integration_identifier": run.plan.integration_identifier,
            "blueprints": run.plan.blueprint_renames,
            "cleaned_up": run.cleaned_up,
            "cleanup_leftovers": run.cleanup_leftovers,
        },
        "integration": _integration_report(run.integration),
    }


def _integration_report(integration: IntegrationRunResult) -> dict[str, Any]:
    return {
        "returncode": integration.returncode,
        "timed_out": integration.timed_out,
        "stderr_tail": _tail(integration.stderr),
        "stdout_tail": _tail(integration.stdout),
    }


def _tail(text: str, *, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _scenario_status(run: ScenarioRun) -> str:
    if run.integration.timed_out:
        return "integration_timeout"
    if run.integration.returncode != 0:
        return "integration_failed"
    return "integration_completed"


def _aggregate_status(result: ValidateResult) -> str:
    statuses = {_scenario_status(run) for run in result.scenario_runs}
    if any(
        status.endswith("failed") or status == "integration_timeout"
        for status in statuses
    ):
        return "failed"
    if statuses == {"integration_completed"}:
        return "passed"
    return "partial"
