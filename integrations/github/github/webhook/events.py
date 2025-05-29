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


ALL_EVENTS = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS + ISSUE_EVENTS


WEBHOOK_CREATE_EVENTS = ["repository", "issues"]
