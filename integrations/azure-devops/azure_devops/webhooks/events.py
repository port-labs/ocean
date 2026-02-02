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


class WorkItemEvents(StrEnum):
    """
    Events for Azure DevOps work item webhooks.
    https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops
    """

    WORK_ITEM_CREATED = "workitem.created"
    WORK_ITEM_UPDATED = "workitem.updated"
    WORK_ITEM_COMMENTED = "workitem.commented"
    WORK_ITEM_DELETED = "workitem.deleted"


class AdvancedSecurityAlertEvents(StrEnum):
    """
    Events for Azure DevOps advanced security alerts webhooks.
    https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops#advanced-security
    """

    SECURITY_ALERT_CREATED = "ms.vss-alerts.alert-created-event"
    SECURITY_ALERT_STATE_CHANGED = "ms.vss-alerts.alert-state-changed-event"
    SECURITY_ALERT_UPDATED = "ms.vss-alerts.alert-updated-event"
