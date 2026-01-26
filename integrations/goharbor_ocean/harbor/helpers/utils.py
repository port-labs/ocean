"""Harbor utility functions and constants."""

from enum import StrEnum

from pydantic import BaseModel


class ObjectKind(StrEnum):
    """Enum for Harbor resource kinds."""

    PROJECT = "project"
    USER = "user"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"


class IgnoredError(BaseModel):
    """Represents an HTTP error that should be gracefully ignored."""

    status: int
    message: str
