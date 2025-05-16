from enum import StrEnum


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    ISSUE = "issue"


class RepositoryType(StrEnum):
    ALL = "all"  # All repositories
    PUBLIC = "public"  # Public repositories
    PRIVATE = "private"  # Private repositories


class IssueState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"
