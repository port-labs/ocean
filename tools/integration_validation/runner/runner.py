from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from tools.integration_validation.runner.port.blueprints import (
    rewrite_mapping_blueprints,
    suffix_blueprints,
)
from tools.integration_validation.runner.results.collect import (
    ScenarioCollection,
    collect_scenario,
)
from tools.integration_validation.runner.core.errors import ValidationSetupError
from tools.integration_validation.runner.scenarios.loader import (
    load_blueprints_file,
    load_port_app_config_file,
    load_scenarios_document,
    resolve_integration_resource_path,
    resolve_scenario_blueprints_path,
    resolve_validation_paths,
)
from tools.integration_validation.runner.core.models import (
    ScenariosDocument,
    ValidationPaths,
)
from tools.integration_validation.runner.core.naming import build_integration_identifier
from tools.integration_validation.runner.port.app_config import (
    build_scenario_port_app_config,
)
from tools.integration_validation.runner.port.client import (
    ScenarioPortPlan,
    ValidationPortClient,
    create_port_client,
    prepare_scenario_port,
    teardown_scenario_port,
)
from tools.integration_validation.runner.integration.config_env import (
    merge_scenario_integration_config,
)
from tools.integration_validation.runner.integration.process import (
    IntegrationRunResult,
    run_ocean_sail_once,
)
from tools.integration_validation.runner.scenarios.preflight import (
    load_integration_type,
    run_preflight,
    select_scenario_names,
)
from tools.integration_validation.runner.core.statuses import (
    ScenarioIntegrationStatus,
    ValidationAggregateStatus,
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
    collection: ScenarioCollection


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
        _run_plans(paths, scenarios, plans, integration_type, options)
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


async def _run_plans(
    paths: ValidationPaths,
    scenarios: ScenariosDocument,
    plans: list[ScenarioPortPlan],
    integration_type: str,
    options: ValidateOptions,
) -> list[ScenarioRun]:
    return [
        await _run_scenario(paths, scenarios, plan, integration_type, options)
        for plan in plans
    ]


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
        collection = await collect_scenario(
            client, plan, mock_base_url=options.mock_base_url
        )
    finally:
        if prepared:
            leftovers = await _teardown_scenario(client, plan, options)

    return ScenarioRun(
        plan=plan,
        cleanup_leftovers=leftovers,
        cleaned_up=prepared and not options.skip_cleanup and not leftovers,
        integration=integration_result,
        collection=collection,
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
        "status": run.integration.integration_status(),
        "kinds": run.plan.kinds,
        "port": {
            "integration_identifier": run.plan.integration_identifier,
            "blueprints": run.plan.blueprint_renames,
            "cleaned_up": run.cleaned_up,
            "cleanup_leftovers": run.cleanup_leftovers,
        },
        "integration": run.integration.report_dict(),
        "collection": run.collection.to_dict(),
    }


def _aggregate_status(result: ValidateResult) -> ValidationAggregateStatus:
    if all(
        run.integration.integration_status() == ScenarioIntegrationStatus.COMPLETED
        for run in result.scenario_runs
    ):
        return ValidationAggregateStatus.PASSED
    return ValidationAggregateStatus.FAILED
