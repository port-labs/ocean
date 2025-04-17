from enum import StrEnum


class PullRequestEvents(StrEnum):
    PULL_REQUEST_CREATED = "git.pullrequest.created"
    PULL_REQUEST_UPDATED = "git.pullrequest.updated"


class PushEvents(StrEnum):
    PUSH = "git.push"

