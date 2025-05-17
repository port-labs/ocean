from enum import StrEnum


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"


class RepositoryType(StrEnum):
    ALL = "all"  # All repositories
    PUBLIC = "public"  # Public repositories
    PRIVATE = "private"  # Private repositories


class PullRequestState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"
