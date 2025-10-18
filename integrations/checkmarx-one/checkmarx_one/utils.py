from enum import StrEnum
from typing import NamedTuple, Optional, List
from datetime import datetime, timedelta, timezone


class ObjectKind(StrEnum):
    """Enum for Checkmarx One resource kinds."""

    PROJECT = "project"
    SCAN = "scan"
    API_SEC = "api-security"
    SAST = "sast"
    KICS = "kics"
    DAST_SCAN_ENVIRONMENT = "dast-scan-environment"
    DAST_SCAN = "dast-scan"
    DAST_SCAN_RESULT = "dast-scan-result"


class ScanResultObjectKind(StrEnum):
    """Enum for Checkmarx One scan result resource kinds."""

    SCA = "sca"
    CONTAINERS = "containers"


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


def sast_visible_columns() -> List[str]:
    """Columns to request for SAST results (API hyphenated keys) including scan-id."""
    return [
        "scan-id",
        "result-hash",
        "result-id",
        "path-system-id",
        "query-ids",
        "query-name",
        "language",
        "group",
        "cwe-id",
        "severity",
        "similarity-id",
        "confidence-level",
        "compliance",
        "first-time-scan-id",
        "first-found-at",
        "status",
        "state",
        "nodes",
    ]


def days_ago_to_rfc3339(days: int) -> str:
    """
    Convert days ago to RFC3339 format.

    Args:
        days: Number of days ago from current time

    Returns:
        RFC3339 formatted datetime string (e.g., 2021-06-02T12:14:18.028555Z)
    """
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    # Format to RFC3339 with microseconds and Zulu time
    # RFC3339 Date (Extend) format (e.g. 2021-06-02T12:14:18.028555Z)
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
