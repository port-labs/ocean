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


ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS
    + REPOSITORY_DELETE_EVENTS
    + PULL_REQUEST_EVENTS
    + ISSUE_EVENTS
)


WEBHOOK_CREATE_EVENTS = ["repository", "pull_request", "issues", "push"]
