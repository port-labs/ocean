"""Gather everything a scenario's resync produced, before cleanup deletes it."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.mock_journal import (
    MockJournal,
    fetch_mock_journal,
)
from tools.integration_validation.runner.port_setup import (
    ScenarioPortPlan,
    ValidationPortClient,
    port_error,
)
from tools.integration_validation.runner.statuses import ResyncStatus


@dataclass(frozen=True)
class ScenarioCollection:
    resync_status: ResyncStatus
    # Keyed by the blueprint identifier in the integration's blueprints file;
    # entity payloads are as Port returned them (suffixed blueprint names).
    entities: dict[str, list[dict[str, Any]]]
    mock: MockJournal

    def report_dict(self) -> dict[str, Any]:
        return {
            "resync_status": self.resync_status.value,
            "entity_counts": {
                blueprint: len(entities)
                for blueprint, entities in self.entities.items()
            },
            "mock": self.mock.report_dict(),
        }


async def collect_scenario(
    client: ValidationPortClient,
    plan: ScenarioPortPlan,
    *,
    mock_base_url: str,
) -> ScenarioCollection:
    """Read the run's Port state and the mock journal.

    Runs after ``ocean sail -O`` exits, which only happens once Ocean has
    reported the final resync status, so nothing here waits or polls.
    """
    try:
        resync_status = await client.get_resync_status()
        entities = await _search_run_entities(client, plan.blueprint_renames)
    except httpx.HTTPStatusError as exc:
        raise port_error(plan.scenario_name, exc) from exc
    except httpx.HTTPError as exc:
        raise ValidationSetupError(
            f"Scenario '{plan.scenario_name}': could not reach Port: {exc}"
        ) from exc

    return ScenarioCollection(
        resync_status=resync_status,
        entities=entities,
        mock=await fetch_mock_journal(mock_base_url),
    )


async def _search_run_entities(
    client: ValidationPortClient, blueprint_renames: dict[str, str]
) -> dict[str, list[dict[str, Any]]]:
    results = await asyncio.gather(
        *(
            client.search_blueprint_entities(suffixed)
            for suffixed in blueprint_renames.values()
        )
    )
    return dict(zip(blueprint_renames, results))
