from enum import StrEnum


class ObjectKind(StrEnum):
    """Enum for Checkmarx One resource kinds."""

    PROJECT = "project"
    SCAN = "scan"
