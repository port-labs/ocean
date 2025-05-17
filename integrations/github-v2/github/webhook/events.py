# Repository events
REPOSITORY_UPSERT_EVENTS = [
    "created",
    "edited",
    "renamed",
    "transferred",
    "archived",
    "unarchived",
]
REPOSITORY_DELETE_EVENTS = ["deleted"]

WORKFLOW_UPSERT_EVENTS = ["in_progress", "requested"]
WORKFLOW_DELETE_EVENTS = ["completed"]

ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS
    + REPOSITORY_DELETE_EVENTS
    + WORKFLOW_DELETE_EVENTS
    + WORKFLOW_UPSERT_EVENTS
)


WEBHOOK_CREATE_EVENTS = ["repository", "workflow_run"]
