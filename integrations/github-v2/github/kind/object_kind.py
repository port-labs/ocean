from enum import StrEnum


class ObjectKind(StrEnum):
    """Enum for GitHub resource kinds."""
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    FILE = "file"