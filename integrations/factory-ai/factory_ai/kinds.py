from enum import StrEnum


class ObjectKind(StrEnum):
    ENVIRONMENT = "environment"
    SESSION = "session"
    COMPUTER = "computer"
    AUTOMATION = "automation"
    SERVICE_ACCOUNT = "service-account"
    WIKI = "wiki"
