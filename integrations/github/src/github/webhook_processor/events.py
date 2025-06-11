from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel


class GitHubWebhookEvent(StrEnum):
    """preferred events for GitHub webhooks"""

    ISSUES = "issues"
    PR = "pull_request"
    REPOSITORY = "repository"
    TEAM = "team_add"
    WORKFLOW = "workflow_job"


class GitHubWebhookEventType(StrEnum):
    """supported event types for GitHub webhooks"""

    REPOSITORY = "Repository"


class WebhookEventPayloadConfig(BaseModel):
    """config section for webhook payload"""

    url: str
    content_type: str
    insecure_ssl: str
    secret: Optional[str] = None


class WebhookEventPayload(BaseModel):
    """payload for webhook event when created/updated"""

    type: GitHubWebhookEventType
    active: bool
    events: list[GitHubWebhookEvent]
    name: str
    updated_at: datetime
    created_at: datetime
    config: Optional[WebhookEventPayloadConfig] = None


class CreateWebhookEventRequest(BaseModel):
    name: str
    events: list[GitHubWebhookEvent]
    config: WebhookEventPayloadConfig
    active: bool = True
    repo_slug: Optional[str] = None
