from dataclasses import dataclass
from enum import Enum
from typing import List

class WebhookEvent(Enum):
    """Enumeration of supported webhook events."""
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    ISSUES = "issues"
    WORKFLOW_RUN = "workflow_run"

@dataclass
class WebhookConfig:
    """Configuration for GitHub webhooks."""
    url: str
    secret: str
    events: List[WebhookEvent]
    content_type: str = "json"
    insecure_ssl: str = "0" 