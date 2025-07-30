from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger
from .base_webhook_processor import BaseAikidoWebhookProcessor
from integration import ObjectKind


class RepositoryWebhookProcessor(BaseAikidoWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue_id = payload["payload"]["issue_id"]
        if not issue_id:
            logger.error("No issue_id found in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        issue = await self._webhook_client.get_issue(issue_id)
        if not issue:
            logger.error(f"No issue details found for issue_id: {issue_id}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        code_repo_id = issue.get("code_repo_id")
        if not code_repo_id:
            logger.error(
                f"No code_repo_id found in issue details for issue_id: {issue_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        repo = await self._webhook_client.get_repository(code_repo_id)
        if not repo:
            logger.error(
                f"No repository details found for code_repo_id: {code_repo_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[repo],
            deleted_raw_results=[],
        )
