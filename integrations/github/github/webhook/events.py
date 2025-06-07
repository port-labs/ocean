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

ALL_EVENTS = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS


WEBHOOK_CREATE_EVENTS = ["repository", "create", "delete", "push"]
