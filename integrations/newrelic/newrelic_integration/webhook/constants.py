WEBHOOK_PATH = "/events"
DEFAULT_ISSUE_KIND = "newRelicAlert"
ISSUE_ENTITY_TYPE = "ISSUE"
SERVICE_DEPENDENCY_KIND = "newRelicServiceDependency"
RESYNC_ONLY_KINDS = frozenset(
    {"newRelicServiceLevel", "newRelicAlertCondition", SERVICE_DEPENDENCY_KIND}
)
