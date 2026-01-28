from enum import StrEnum


class HarborResourceType(StrEnum):
    """Enum representing Harbor resource types."""

    PROJECT = "project"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"
    TAG = "tag"
    USER = "user"
