from enum import StrEnum


class PullRequestEvents(StrEnum):
    """
    Events for Azure DevOps webhooks.
    https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops
    """

    PULL_REQUEST_CREATED = "git.pullrequest.created"
    PULL_REQUEST_UPDATED = "git.pullrequest.updated"


class PushEvents(StrEnum):
    PUSH = "git.push"


class RepositoryEvents(StrEnum):
    REPO_CREATED = "git.repo.created"
