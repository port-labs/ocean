# supported actions for custom internal integration webhooks
DELETE_ACTION: str = "ignored"
EVENT_ACTIONS: list[str] = [
    "created",
    "unresolved",
    "resolved",
    "assigned",
    DELETE_ACTION,
]
