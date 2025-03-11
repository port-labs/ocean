SERVICE_DELETE_EVENTS = ["service.deleted"]
SERVICE_UPSERT_EVENTS = [
    "service.created",
    "service.updated",
]

INCIDENT_UPSERT_EVENTS = [
    "incident.acknowledged",
    "incident.annotated",
    "incident.delegated",
    "incident.escalated",
    "incident.priority_updated",
    "incident.reassigned",
    "incident.reopened",
    "incident.resolved",
    "incident.status_update_published",
    "incident.responder.added",
    "incident.responder.replied",
    "incident.triggered",
    "incident.unacknowledged",
]

ALL_EVENTS = SERVICE_UPSERT_EVENTS + INCIDENT_UPSERT_EVENTS + SERVICE_DELETE_EVENTS
