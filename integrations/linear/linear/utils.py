from enum import StrEnum


class ObjectKind(StrEnum):
    """Object kinds for Linear integration."""

    TEAM = "team"
    LABEL = "label"
    ISSUE = "issue"


class WebhookAction(StrEnum):
    """Enum representing possible webhook actions from Linear."""

    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
