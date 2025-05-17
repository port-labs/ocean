from enum import StrEnum


class ObjectKind(StrEnum):
    REPOSITORY = "repository"


class RepositoryType(StrEnum):
    ALL = "all"  # All repositories
    PUBLIC = "public"  # Public repositories
    PRIVATE = "private"  # Private repositories
