from typing import List
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults, EventPayload, EventHeaders
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from github.client import GitHubClient
from initialize_client import create_github_client
from integration import PullRequestResourceConfig
from utils import ObjectKind

class PullRequestWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("X-GitHub-Event") == "pull_request"

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return [ObjectKind.PULL_REQUEST]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        signature = headers.get("X-Hub-Signature-256")
        if signature:
            return create_github_client().verify_webhook_signature(payload, signature)
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "pull_request" in payload and "action" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_github_client()
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        if not pr:
            return WebhookEventRawResults([], [])
        repo = pr["base"]["repo"]["full_name"]
        pr_number = pr["number"]
        if action in ["opened", "edited", "reopened", "closed", "synchronize"]:
            latest_pr = await client._send_api_request(
                "GET", f"repos/{repo}/pulls/{pr_number}"
            )
            if latest_pr:
                return WebhookEventRawResults([latest_pr], [])
        return WebhookEventRawResults([], [])