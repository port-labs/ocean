from enum import StrEnum


class CheckmarxEventType(StrEnum):
    """Enum for Checkmarx One event types."""

    PROJECT_CREATED = "project.created"
    SCAN_COMPLETED = "scan_completed_successfully"
    SCAN_FAILED = "scan_failed"
    SCAN_PARTIAL = "scan_partial"
