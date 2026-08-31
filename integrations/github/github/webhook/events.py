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

USER_UPSERT_EVENTS = ["member_added"]
USER_DELETE_EVENTS = ["member_removed"]

WORKFLOW_UPSERT_EVENTS = ["completed", "in_progress", "requested"]

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
    "labeled",
    "unlabeled",
    "assigned",
    "review_requested",
    "converted_to_draft",
    "locked",
    "unlocked",
    "auto_merge_enabled",
    "auto_merge_disabled",
    "milestoned",
    "demilestoned",
    "dequeued",
    "enqueued",
    "stacked",
]

# Pull request review events (separate GitHub event type: pull_request_review)
PULL_REQUEST_REVIEW_EVENTS = ["submitted", "edited", "dismissed"]

# Check run validation only fires for these PR actions
CHECK_RUN_PR_ACTIONS = ["opened", "synchronize", "reopened", "edited"]

TEAM_UPSERT_EVENTS = ["created", "edited"]
TEAM_DELETE_EVENTS = ["deleted"]
MEMBERSHIP_ADDED_EVENTS = ["added"]
MEMBERSHIP_DELETE_EVENTS = ["removed"]
TEAM_MEMBERSHIP_EVENTS = MEMBERSHIP_ADDED_EVENTS + MEMBERSHIP_DELETE_EVENTS


TEAM_EVENTS = TEAM_UPSERT_EVENTS + TEAM_DELETE_EVENTS
USER_EVENTS = USER_UPSERT_EVENTS + USER_DELETE_EVENTS

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

WORKFLOW_RUN_EVENTS = WORKFLOW_UPSERT_EVENTS

DEPENDABOT_ACTION_TO_STATE = {
    "created": "open",
    "reopened": "open",
    "auto_reopened": "open",
    "reintroduced": "open",
    "dismissed": "dismissed",
    "auto_dismissed": "auto_dismissed",
    "fixed": "fixed",
}

DEPENDABOT_ALERT_EVENTS = list(DEPENDABOT_ACTION_TO_STATE.keys())


CODE_SCANNING_ALERT_ACTION_TO_STATE = {
    "appeared_in_branch": ["open"],
    "reopened": ["open"],
    "created": ["open"],
    "fixed": ["fixed", "dismissed"],
    "closed_by_user": ["closed"],
}

CODE_SCANNING_ALERT_EVENTS = list(CODE_SCANNING_ALERT_ACTION_TO_STATE.keys())


SECRET_SCANNING_ALERT_ACTION_TO_STATE = {
    "created": ["open"],
    "publicly_leaked": ["open"],
    "reopened": ["open"],
    "validated": ["open"],
    "resolved": ["resolved"],
}

SECRET_SCANNING_ALERT_EVENTS = list(SECRET_SCANNING_ALERT_ACTION_TO_STATE.keys())

PACKAGE_UPSERT_EVENTS = ["published", "updated"]
PACKAGE_EVENTS = PACKAGE_UPSERT_EVENTS


# Collaborator events
COLLABORATOR_UPSERT_EVENTS = ["added", "created", "edited"]
COLLABORATOR_DELETE_EVENTS = ["removed", "deleted"]
TEAM_COLLABORATOR_EVENTS = ["added_to_repository"]
COLLABORATOR_EVENTS = COLLABORATOR_UPSERT_EVENTS + COLLABORATOR_DELETE_EVENTS


ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS
    + REPOSITORY_DELETE_EVENTS
    + PULL_REQUEST_EVENTS
    + ISSUE_EVENTS
    + TEAM_EVENTS
    + USER_EVENTS
    + RELEASE_EVENTS
    + WORKFLOW_RUN_EVENTS
    + DEPENDABOT_ALERT_EVENTS
    + CODE_SCANNING_ALERT_EVENTS
    + COLLABORATOR_EVENTS
    + TEAM_COLLABORATOR_EVENTS
    + SECRET_SCANNING_ALERT_EVENTS
    + PACKAGE_EVENTS
)


WEBHOOK_CREATE_EVENTS = [
    "repository",
    "pull_request",
    "pull_request_review",
    "issues",
    "release",
    "create",
    "delete",
    "push",
    "deployment",
    "deployment_status",
    "workflow_run",
    "dependabot_alert",
    "code_scanning_alert",
    "organization",
    "team",
    "membership",
    "member",
    "secret_scanning_alert",
    "package",
]
