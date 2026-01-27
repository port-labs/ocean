# supported actions for custom internal integration webhooks
ARCHIVED_ISSUE_ACTION: str = "ignored"
ISSUE_EVENT_ACTIONS: list[str] = [
    "created",
    "unresolved",
    "resolved",
    "assigned",
    ARCHIVED_ISSUE_ACTION,
]
