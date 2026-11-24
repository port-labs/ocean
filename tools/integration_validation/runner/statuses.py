from __future__ import annotations

from enum import StrEnum


class ScenarioIntegrationStatus(StrEnum):
    TIMEOUT = "integration_timeout"
    FAILED = "integration_failed"
    COMPLETED = "integration_completed"


class ValidationAggregateStatus(StrEnum):
    FAILED = "failed"
    PASSED = "passed"
