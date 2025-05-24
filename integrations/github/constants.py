"""Constants used throughout the GitHub integration."""

from enum import StrEnum

class ObjectKind(StrEnum):
    """Enum for GitHub object kinds."""
    REPOSITORY = "repository"
    ISSUE = "issue"
    PULLREQUEST = "pull-request"
    WORKFLOW = "workflow"
    TEAM = "team"
