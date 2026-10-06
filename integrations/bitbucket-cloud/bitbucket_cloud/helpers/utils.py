from enum import StrEnum
from dataclasses import dataclass
from typing import NamedTuple, Optional


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    body_contains: Optional[str] = None


class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    FILE = "file"


@dataclass
class BitbucketRateLimiterConfig:
    """Configuration for Bitbucket API rate limiting."""

    WINDOW: int = 3600  # Rate limit window in seconds
    LIMIT: int = 980  # Number of requests allowed per window


@dataclass
class BitbucketFileRateLimiterConfig:
    """Configuration for Bitbucket file content API rate limiting."""

    WINDOW: int = 3600  # Rate limit window in seconds
    LIMIT: int = 4980  # Number of requests allowed per window for file operations
