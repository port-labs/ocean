from loguru import logger

from github.webhooks_processors.processors._abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from github.webhooks_processors.events import Events
from github.kind.object_kind import ObjectKind


WEBHOOK_NAME = "GithubIssueWebhook"


class GithubIssueWebhookProcessor(BaseWebhookProcessorMixin):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = self._get_github_event_type(event.headers)
        if event_type != Events.ISSUES.value:
            logger.info(f"[{WEBHOOK_NAME}] Skipping event type: {event_type}")
            return False
        logger.info(f"[{WEBHOOK_NAME}] Processing issues event: action={event.payload.get('action')}")
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE.value]

    async def validate_payload(self, payload: EventPayload) -> bool:
        has_issue = isinstance(payload, dict) and isinstance(payload.get("issue"), dict)
        has_repo = isinstance(payload.get("repository"), dict) and isinstance(
            payload["repository"].get("name"), str
        )
        if not (has_issue and has_repo):
            logger.warning(f"[{WEBHOOK_NAME}] Invalid payload structure for issues webhook")
            return False
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue = dict(payload.get("issue", {}))
        repository = payload.get("repository", {})
        repo_name = repository.get("name")

        if repo_name:
            issue["__repository"] = repo_name

        # Return the issue object as-is (with __repository added) so JQ mappings can apply
        result = WebhookEventRawResults(updated_raw_results=[issue], deleted_raw_results=[])

        logger.info(f"[{WEBHOOK_NAME}] Handle event result = {len(result.updated_raw_results)}")
        
        return result


