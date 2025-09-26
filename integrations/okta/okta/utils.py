from enum import StrEnum


class ObjectKind(StrEnum):
    """Okta object kinds used across the integration."""

    USER = "okta-user"
    GROUP = "okta-group"
