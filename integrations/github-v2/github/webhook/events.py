from typing import Literal

# GitHub webhook events
GitHubWebhookEvent = Literal[
    "push",
    "pull_request",
    "issues",
    "workflow_run",
    "team",
    "repository",
    "create",
    "delete",
    "release",
    "star",
    "watch",
    "fork",
]

# GitHub webhook actions
GitHubWebhookAction = Literal[
    "opened",
    "closed",
    "reopened",
    "edited",
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
    "synchronize",
    "ready_for_review",
    "converted_to_draft",
    "completed",
    "requested",
    "created",
    "deleted",
    "published",
    "unpublished",
    "released",
    "prereleased",
]
