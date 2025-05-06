# Build Events
BUILD_UPSERT_EVENTS = [
    "run.initialize",
    "run.started",
    "run.completed",
    "run.finalized",
]
BUILD_DELETE_EVENTS = ["run.deleted"]

# Job events
JOB_UPSERT_EVENTS = ["item.created", "item.updated"]
JOB_DELETE_EVENTS = ["item.deleted"]
