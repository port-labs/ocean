# Repository events
REPOSITORY_UPSERT_EVENTS = [
    "created",
    "edited",
    "renamed",
    "transferred",
    "archived",
    "unarchived"
]
REPOSITORY_DELETE_EVENTS = ["deleted"]

# Pull request events
PULL_REQUEST_UPSERT_EVENTS = [
    "opened",
    "closed",
    "reopened",
    "edited",
    "merged"
]
PULL_REQUEST_DELETE_EVENTS = ["deleted"]

# Issue events
ISSUE_UPSERT_EVENTS = [
    "opened",
    "closed",
    "reopened",
    "edited"
]
ISSUE_DELETE_EVENTS = ["deleted"]

# Team events
TEAM_UPSERT_EVENTS = [
    "created",
    "edited"
]
TEAM_DELETE_EVENTS = ["deleted"]

# Workflow events
WORKFLOW_EVENTS = ["workflow_run"]

ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS 
    + REPOSITORY_DELETE_EVENTS
    + PULL_REQUEST_UPSERT_EVENTS
    + PULL_REQUEST_DELETE_EVENTS
    + ISSUE_UPSERT_EVENTS
    + ISSUE_DELETE_EVENTS
    + TEAM_UPSERT_EVENTS
    + TEAM_DELETE_EVENTS
    + WORKFLOW_EVENTS
) 