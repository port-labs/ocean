from enum import StrEnum
from dataclasses import dataclass


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
