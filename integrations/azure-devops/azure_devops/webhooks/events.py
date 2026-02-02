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


class PipelineEvents(StrEnum):
    """
    Events for Azure DevOps pipeline webhooks.
    https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops#pipeline
    """

    PIPELINE_UPDATED = "ms.vss-pipelinechecks-events.check-updated-event"


class PipelineStageEvents(StrEnum):
    """
    Events for Azure DevOps pipeline stage webhooks.
    https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops#run-stage-waiting-for-approval
    """

    PIPELINE_STAGE_STATE_CHANGED = "ms.vss-pipelines.stage-state-changed-event"
    PIPELINE_STAGE_APPROVAL_PENDING = "ms.vss-pipelinechecks-events.approval-pending"
    PIPELINE_STAGE_APPROVAL_COMPLETED = (
        "ms.vss-pipelinechecks-events.approval-completed"
    )


class PipelineRunEvents(StrEnum):
    """
    Events for Azure DevOps pipeline run webhooks.
    https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops#run-state-changed
    """

    PIPELINE_RUN_STATE_CHANGED = "ms.vss-pipelines.run-state-changed-event"
