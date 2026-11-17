from enum import StrEnum


class ObjectKind(StrEnum):
    SESSION = "session"
    COMPUTER = "computer"
    AUTOMATION = "automation"
    SERVICE_ACCOUNT = "service-account"
    WIKI = "wiki"
