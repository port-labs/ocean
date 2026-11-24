from __future__ import annotations

from enum import StrEnum
from typing import assert_never


class ScenarioIntegrationStatus(StrEnum):
    TIMEOUT = "integration_timeout"
    FAILED = "integration_failed"
    COMPLETED = "integration_completed"

    @property
    def is_failure(self) -> bool:
        match self:
            case ScenarioIntegrationStatus.FAILED | ScenarioIntegrationStatus.TIMEOUT:
                return True
            case ScenarioIntegrationStatus.COMPLETED:
                return False
            case _ as unreachable:
                assert_never(unreachable)


class ValidationAggregateStatus(StrEnum):
    FAILED = "failed"
    PASSED = "passed"
    PARTIAL = "partial"
