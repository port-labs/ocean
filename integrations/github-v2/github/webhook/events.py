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


ALL_EVENTS = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS + PULL_REQUEST_EVENTS


WEBHOOK_CREATE_EVENTS = ["repository", "pull_request"]
