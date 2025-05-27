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

DEPENDABOT_ALERT_EVENTS = [
    "auto_reopened",
    "created",
    "reopened",
    "reintroduced",
    "auto_dismissed",
    "dismissed",
    "fixed",
]

CODE_SCANNING_ALERT_UPSERT_EVENTS = [
    "appeared_in_branch",
    "created",
    "fixed",
    "reopened",
    "reopened_by_user",
]
CODE_SCANNING_ALERT_DELETE_EVENTS = ["closed_by_user"]
CODE_SCANNING_ALERT_EVENTS = CODE_SCANNING_ALERT_UPSERT_EVENTS + CODE_SCANNING_ALERT_DELETE_EVENTS


ALL_EVENTS = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS + DEPENDABOT_ALERT_EVENTS + CODE_SCANNING_ALERT_EVENTS


WEBHOOK_CREATE_EVENTS = ["repository", "dependabot_alert", "code_scanning_alert"]
