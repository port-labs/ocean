from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import ObjectKind
from webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)


class PullRequestWebhookProcessor(BaseWebhookProcessorMixin):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload["eventKey"].startswith("pr:")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        event_key = payload["eventKey"]
        pull_request_id = payload["pullRequest"]["id"]
        repository_id = payload["pullRequest"]["toRef"]["repository"]["slug"]
        project_key = payload["pullRequest"]["toRef"]["repository"]["project"]["key"]
        logger.info(
            f"Handling pull request webhook event for repository: {repository_id} and pull request: {pull_request_id}"
        )

        if event_key == "pr:deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["pullRequest"]],
            )

        pull_request_details = await self._client.get_single_pull_request(
            project_key=project_key, repo_slug=repository_id, pr_key=pull_request_id
        )

        return WebhookEventRawResults(
            updated_raw_results=[pull_request_details],
            deleted_raw_results=[],
        )
