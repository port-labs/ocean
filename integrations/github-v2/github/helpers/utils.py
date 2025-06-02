from typing import Literal


class ObjectKind:
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"


# GitHub webhook event types
GitHubEventType = Literal[
    "push",
    "pull_request",
    "issues",
    "workflow_run",
    "team",
    "repository",
]
