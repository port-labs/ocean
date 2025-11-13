from enum import StrEnum

"""Harbor Integration Constants.

This module defines common utilities and enumerations used throughout
the Harbor integration.
"""


class ObjectKind(StrEnum):
    """Enumeration of Harbor resource kinds.

    Defines the different types of resources that can be synced from Harbor
    to Port. Each kind corresponds to a specific Harbor entity type.
    """

    PROJECT = "project"
    USER = "user"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"


# Lists
WEBHOOK_EVENTS = [
    "PUSH_ARTIFACT",
    "DELETE_ARTIFACT",
    "PULL_ARTIFACT",
    "SCANNING_COMPLETED",
    "SCANNING_FAILED",
    "QUOTA_EXCEED",
    "QUOTA_WARNING",
    "REPLICATION",
    "TAG_RETENTION",
]

# Strings
WEBHOOK_NAME = "ocean-port-webhook"

# Numbers
MAX_CONCURRENT_REQUESTS = 10
DEFAULT_PAGE_SIZE = 100
CLIENT_TIMEOUT = 30
