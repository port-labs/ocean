from enum import StrEnum


class HarborResourceType(StrEnum):
    PROJECT = "project"
    USER = "user"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"


class HarborActionType(StrEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    SCAN = "scan"
    PULL = "pull"
    PUSH = "push"


class HarborUserType(StrEnum):
    PROJECT_ADMIN = "ProjectAdmin"
    MAINTAINER = "Maintainer"
    DEVELOPER = "Developer"
    GUEST = "Guest"
    LIMITED_GUEST = "Limited Guest"
    SYSTEM_ADMIN = "SystemAdmin"


class HarborWebhookEventType(StrEnum):
    PUSH_ARTIFACT = "PUSH_ARTIFACT"
    PULL_ARTIFACT = "PULL_ARTIFACT"
    DELETE_ARTIFACT = "DELETE_ARTIFACT"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    REPLICATION_COMPLETED = "REPLICATION_COMPLETED"
