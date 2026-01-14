# supported actions for custom internal integration webhooks
DELETE_ACTION: str = "ignored"
EVENT_ACTIONS: list[str] = [
    "created",
    "unresolved",
    "resolved",
    "assigned",
    DELETE_ACTION,
]

ALERT_RULE_CONDITIONS = [
    {"id": "sentry.rules.conditions.first_seen_event.FirstSeenEventCondition"},
    {"id": "sentry.rules.conditions.regression_event.RegressionEventCondition"},
    {"id": "sentry.rules.conditions.reappeared_event.ReappearedEventCondition"},
]

ALERT_RULE_ACTIONS = [
    {"id": "sentry.rules.actions.notify_event.NotifyEventAction"},
]
