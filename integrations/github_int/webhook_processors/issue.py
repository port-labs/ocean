
from typing import List
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults, EventPayload, EventHeaders
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from github.client import GitHubClient
from initialize_client import create_github_client
from utils import ObjectKind

class IssueWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("X-GitHub-Event") == "issues"

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return [ObjectKind.ISSUE]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        signature = headers.get("X-Hub-Signature-256")
        if signature:
            return create_github_client().verify_webhook_signature(payload, signature)
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "issue" in payload and "action" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_github_client()
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        if not issue:
            return WebhookEventRawResults([], [])
        repo = payload["repository"]["full_name"]
        issue_number = issue["number"]
        if action in ["opened", "edited", "closed", "reopened"]:
            latest_issue = await client._send_api_request(
                "GET", f"repos/{repo}/issues/{issue_number}"
            )
            if latest_issue and not latest_issue.get("pull_request"):  # Ensure it's an issue
                return WebhookEventRawResults([latest_issue], [])
            logger.warning(f"Issue {issue_number} not found or is a pull request")
        return WebhookEventRawResults([], [])
