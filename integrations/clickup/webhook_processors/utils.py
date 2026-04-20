from enum import StrEnum


class WebhookEvent(StrEnum):
    """ClickUp webhook event types.

    Reference: https://developer.clickup.com/docs/webhooks
    """

    TASK_CREATED = "taskCreated"
    TASK_UPDATED = "taskUpdated"
    TASK_DELETED = "taskDeleted"
    TASK_PRIORITY_UPDATED = "taskPriorityUpdated"
    TASK_STATUS_UPDATED = "taskStatusUpdated"
    TASK_ASSIGNEE_UPDATED = "taskAssigneeUpdated"
    TASK_DUE_DATE_UPDATED = "taskDueDateUpdated"
    TASK_TAG_UPDATED = "taskTagUpdated"
    TASK_MOVED = "taskMoved"
    TASK_COMMENT_POSTED = "taskCommentPosted"
    TASK_COMMENT_UPDATED = "taskCommentUpdated"
    TASK_TIME_ESTIMATE_UPDATED = "taskTimeEstimateUpdated"
    TASK_TIME_TRACKED_UPDATED = "taskTimeTrackedUpdated"

    LIST_CREATED = "listCreated"
    LIST_UPDATED = "listUpdated"
    LIST_DELETED = "listDeleted"

    FOLDER_CREATED = "folderCreated"
    FOLDER_UPDATED = "folderUpdated"
    FOLDER_DELETED = "folderDeleted"

    SPACE_CREATED = "spaceCreated"
    SPACE_UPDATED = "spaceUpdated"
    SPACE_DELETED = "spaceDeleted"


TASK_EVENTS = {
    WebhookEvent.TASK_CREATED,
    WebhookEvent.TASK_UPDATED,
    WebhookEvent.TASK_DELETED,
    WebhookEvent.TASK_PRIORITY_UPDATED,
    WebhookEvent.TASK_STATUS_UPDATED,
    WebhookEvent.TASK_ASSIGNEE_UPDATED,
    WebhookEvent.TASK_DUE_DATE_UPDATED,
    WebhookEvent.TASK_TAG_UPDATED,
    WebhookEvent.TASK_MOVED,
    WebhookEvent.TASK_COMMENT_POSTED,
    WebhookEvent.TASK_COMMENT_UPDATED,
    WebhookEvent.TASK_TIME_ESTIMATE_UPDATED,
    WebhookEvent.TASK_TIME_TRACKED_UPDATED,
}

LIST_EVENTS = {
    WebhookEvent.LIST_CREATED,
    WebhookEvent.LIST_UPDATED,
    WebhookEvent.LIST_DELETED,
}

FOLDER_EVENTS = {
    WebhookEvent.FOLDER_CREATED,
    WebhookEvent.FOLDER_UPDATED,
    WebhookEvent.FOLDER_DELETED,
}

SPACE_EVENTS = {
    WebhookEvent.SPACE_CREATED,
    WebhookEvent.SPACE_UPDATED,
    WebhookEvent.SPACE_DELETED,
}

DELETE_EVENTS = {
    WebhookEvent.TASK_DELETED,
    WebhookEvent.LIST_DELETED,
    WebhookEvent.FOLDER_DELETED,
    WebhookEvent.SPACE_DELETED,
}
