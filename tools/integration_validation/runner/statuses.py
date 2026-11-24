from __future__ import annotations

from enum import StrEnum


class ScenarioIntegrationStatus(StrEnum):
    TIMEOUT = "integration_timeout"
    FAILED = "integration_failed"
    COMPLETED = "integration_completed"


class ResyncStatus(StrEnum):
    """Resync state Port reports for the run's integration."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    MISSING = "missing"

    @classmethod
    def from_port(cls, value: str | None) -> ResyncStatus:
        if value is None:
            return cls.MISSING
        try:
            return cls(value)
        except ValueError:
            return cls.MISSING


class ValidationAggregateStatus(StrEnum):
    FAILED = "failed"
    PASSED = "passed"
