# Issue related events
ISSUE_UPSERT_EVENTS = [
    "opened",
    "edited",
    "deleted",
    "transferred",
    "pinned",
    "unpinned",
    "closed",
    "reopened",
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
    "locked",
    "unlocked",
    "milestoned",
    "demilestoned",
]

ISSUE_DELETE_EVENTS = [
    "deleted",
]

# Repository related events
REPOSITORY_EVENTS = [
    "created",
    "deleted",
    "renamed",
]

REPO_DELETE_EVENTS = [
    "deleted",
]

REPO_UPSERT_EVENTS = [
    "created",
    "deleted",
    "renamed",
    "edited",
    "archived",
    "unarchived",
    "pinned",
    "unpinned",
    "locked",
    "unlocked",
    "transferred",
]

# Pull request related events
PULL_REQUEST_EVENTS = [
    "opened",
    "edited",
    "deleted",
    "transferred",
]

PR_DELETE_EVENTS = [
    "deleted",
]

PR_UPSERT_EVENTS = [
    "opened",
    "edited",
    "closed",
    "reopened",
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
    "locked",
    "unlocked",
    "milestoned",
    "demilestoned",
]

PR_COMMENT_EVENTS = [
    "created",
    "edited",
    "deleted",
]

PR_REVIEW_EVENTS = [
    "submitted",
    "edited",
    "dismissed",
]

# Team related events
TEAM_EVENTS = [
    "created",
    "deleted",
    "edited",
    "added_to_repository",
    "removed_from_repository",
]

TEAM_DELETE_EVENTS = [
    "deleted",
]

TEAM_UPSERT_EVENTS = [
    "created",
    "deleted",
    "edited",
]

# Workflow related events
WORKFLOW_EVENTS = [
    "created",
    "deleted",
    "edited",
    "activated",
    "deactivated",
]

WORKFLOW_RUN_EVENTS = [
    "completed",
    "requested",
    "rerequested",
    "cancelled",
    "requested_action",
]

WORKFLOW_DELETE_EVENTS = [
    "deleted",
]

WORKFLOW_UPSERT_EVENTS = [
    "created",
    "deleted",
    "edited",
    "activated",
    "deactivated",
]