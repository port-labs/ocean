from enum import StrEnum


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    WORKFLOW = "workflow"
    WORKFLOW_RUN = "workflow-run"


class RepositoryType(StrEnum):
    ALL = "all"  # All repositories
    PUBLIC = "public"  # Public repositories
    PRIVATE = "private"  # Private repositories
