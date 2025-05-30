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

TEAM_UPSERT_EVENTS = ["created", "edited"]
TEAM_DELETE_EVENTS = ["deleted"]

ALL_EVENTS = (
    REPOSITORY_UPSERT_EVENTS
    + REPOSITORY_DELETE_EVENTS
    + USER_UPSERT_EVENTS
    + USER_DELETE_EVENTS
    + TEAM_UPSERT_EVENTS
    + TEAM_DELETE_EVENTS
)

WEBHOOK_CREATE_EVENTS = ["repository", "organization", "team"]
