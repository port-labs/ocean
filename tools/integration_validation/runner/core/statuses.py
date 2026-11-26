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


class ComparisonStatus(StrEnum):
    """Outcome of comparing a scenario's entities with ``expected/<scenario>/``."""

    MATCHED = "matched"
    DIFFERENT = "different"
    # No expected files yet; they were written from this run.
    NEW = "new"
    # ``--update-expected`` overwrote the expected files.
    UPDATED = "updated"
    # The resync did not complete, so there was nothing trustworthy to write.
    SKIPPED = "skipped"


class ValidationAggregateStatus(StrEnum):
    FAILED = "failed"
    PASSED = "passed"
    # A setup or Port error stopped the run.
    ERROR = "error"
