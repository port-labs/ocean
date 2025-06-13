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

RELEASE_UPSERT_EVENTS = [
    "created",
    "edited",
]
RELEASE_DELETE_EVENTS = ["deleted"]
RELEASE_EVENTS = RELEASE_UPSERT_EVENTS + RELEASE_DELETE_EVENTS


DEPENDABOT_ALERT_EVENTS = [
    "auto_reopened",
    "created",
    "reopened",
    "reintroduced",
    "auto_dismissed",
    "dismissed",
    "fixed",
]

DEPENDABOT_ACTION_TO_STATE = {
    "created": "open",
    "reopened": "open",
    "auto_reopened": "open",
    "dismissed": "dismissed",
    "auto_dismissed": "auto_dismissed",
    "fixed": "fixed",
}

CODE_SCANNING_ALERT_EVENTS = [
    "appeared_in_branch",
    "created",
    "fixed",
    "reopened",
    "reopened_by_user",
    "closed_by_user",
]
CODE_SCANNING_ALERT_ACTION_TO_STATE = {
    "appeared_in_branch": ["open"],
    "reopened_by_user": ["open"],
    "reopened": ["open"],
    "created": ["open"],
    "fixed": ["fixed", "dismissed"],
    "closed_by_user": ["dismissed"],
}


ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS
    + REPOSITORY_DELETE_EVENTS
    + PULL_REQUEST_EVENTS
    + ISSUE_EVENTS
    + RELEASE_EVENTS
    + DEPENDABOT_ALERT_EVENTS
    + CODE_SCANNING_ALERT_EVENTS
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
    "dependabot_alert",
    "code_scanning_alert",
]
