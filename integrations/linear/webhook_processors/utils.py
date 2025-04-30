from enum import StrEnum


class WebhookAction(StrEnum):
    """Enum representing possible webhook actions from Linear."""

    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
