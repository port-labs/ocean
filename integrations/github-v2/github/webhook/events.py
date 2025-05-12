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

ALL_EVENTS = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS


WEBHOOK_CREATE_EVENTS = ["repository"]
