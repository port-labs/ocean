# Aikido webhook events configuration

from enum import StrEnum


class Events(StrEnum):
    """Webhook events."""

    PING = "ping"  # Sent once when webhook is created

    REPOSITORY = "repository"  # Repo created, renamed, deleted
    ISSUES = "issues"  # Issue opened, edited, closed, etc.
    PULL_REQUEST = "pull_request"  # PR opened, closed, merged, edited
    PULL_REQUEST_REVIEW = "pull_request_review"  # Reviews on PRs

