# Repository events
REPOSITORY_UPSERT_EVENTS = [
    "created",
    "edited",
    "renamed",
    "transferred",
    "unarchived",
    "publicized",
    "privatized",
]
REPOSITORY_DELETE_EVENTS = ["archived", "deleted"]

WORKFLOW_UPSERT_EVENTS = ["in_progress", "requested"]
WORKFLOW_DELETE_EVENTS = ["completed"]

# Pull request events
PULL_REQUEST_EVENTS = [
    "opened",
    "edited",
    "ready_for_review",
    "reopened",
    "synchronize",
    "unassigned",
    "review_request_removed",
    "closed",
]


# Issue events
ISSUE_UPSERT_EVENTS = [
    "assigned",
    "closed",
    "demilestoned",
    "edited",
    "labeled",
    "locked",
    "milestoned",
    "opened",
    "pinned",
    "reopened",
    "transferred",
    "typed",
    "unassigned",
    "unlabeled",
    "unlocked",
    "unpinned",
    "untyped",
]
ISSUE_DELETE_EVENTS = ["deleted"]
ISSUE_EVENTS = ISSUE_UPSERT_EVENTS + ISSUE_DELETE_EVENTS

RELEASE_UPSERT_EVENTS = [
    "created",
    "edited",
]
RELEASE_DELETE_EVENTS = ["deleted"]
RELEASE_EVENTS = RELEASE_UPSERT_EVENTS + RELEASE_DELETE_EVENTS

WORKFLOW_RUN_EVENTS = WORKFLOW_DELETE_EVENTS + WORKFLOW_UPSERT_EVENTS

ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS
    + REPOSITORY_DELETE_EVENTS
    + PULL_REQUEST_EVENTS
    + ISSUE_EVENTS
    + RELEASE_EVENTS
    + WORKFLOW_RUN_EVENTS
)

WEBHOOK_CREATE_EVENTS = [
    "repository",
    "pull_request",
    "issues",
    "release",
    "create",
    "delete",
    "push",
    "deployment",
    "deployment_status",
    "workflow_run",
]
