"""Judge a scenario's collected entities against its expected snapshots."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from tools.integration_validation.runner.core.models import EntitiesByBlueprint
from tools.integration_validation.runner.core.statuses import ComparisonStatus
from tools.integration_validation.runner.results.compare import (
    BlueprintDiff,
    diff_entities,
)
from tools.integration_validation.runner.results.expected import (
    load_expected,
    write_expected,
)
from tools.integration_validation.runner.results.normalize import normalize_entities


class ScenarioComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ComparisonStatus
    expected_dir: Path
    entity_diff: dict[str, BlueprintDiff]

    @property
    def difference_count(self) -> int:
        return sum(
            len(diff.added) + len(diff.removed) + len(diff.changed)
            for diff in self.entity_diff.values()
        )

    @property
    def passed(self) -> bool:
        return self.status == ComparisonStatus.MATCHED


def evaluate_scenario(
    entities: EntitiesByBlueprint,
    *,
    expected_dir: Path,
    ignore_fields: list[str],
    update_expected: bool,
    resync_succeeded: bool,
) -> ScenarioComparison:
    """Diff ``entities`` (keyed by real blueprint) with the scenario's snapshots.

    On a first run or with ``--update-expected`` the snapshots are written from
    this run first, so the scenario matches. A failed resync never writes, so a
    broken run never becomes the expected state.
    """
    actual = normalize_entities(entities, ignore_fields)
    expected = load_expected(expected_dir)

    if resync_succeeded and (update_expected or expected is None):
        write_expected(expected_dir, actual)
        expected = actual

    entity_diff = diff_entities(
        normalize_entities(expected or {}, ignore_fields), actual
    )
    return ScenarioComparison(
        status=ComparisonStatus.DIFFERENT if entity_diff else ComparisonStatus.MATCHED,
        expected_dir=expected_dir,
        entity_diff=entity_diff,
    )
