from enum import StrEnum

WEBHOOK_PATH = "/webhook"


class WebhookPayloadKey(StrEnum):
    PAGE = "page"
    INCIDENT = "incident"
    INCIDENT_UPDATES = "incident_updates"
