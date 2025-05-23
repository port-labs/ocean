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

DEPLOYMENT_EVENTS = ["created"]

ALL_EVENTS = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS + DEPLOYMENT_EVENTS


WEBHOOK_CREATE_EVENTS = ["repository", "deployment"]
