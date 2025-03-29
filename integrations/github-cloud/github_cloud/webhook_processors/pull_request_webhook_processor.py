from loguru import logger
from github_cloud.helpers.constants import PULL_REQUEST_DELETE_EVENTS, PULL_REQUEST_UPSERT_EVENTS
from github_cloud.helpers.utils import ObjectKind
from initialize_client import init_client
from github_cloud.webhook_processors.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class PullRequestWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")

        return (
            event_name == "pull_request" and event_type in PULL_REQUEST_UPSERT_EVENTS + PULL_REQUEST_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repo_name = payload.get("repository", {}).get("name")
        pr_number = pr.get("number")

        logger.info(
            f"Processing pull request event: {action} for PR #{pr_number} in {repo_name}"
        )

        if action in PULL_REQUEST_DELETE_EVENTS:
            logger.info(f"Pull request #{pr_number} was deleted in {repo_name}")

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[pr],
            )

        client = init_client()
        latest_pr = await client.get_single_resource(ObjectKind.PULL_REQUEST, f"{repo_name}/{pr_number}")

        logger.info(f"Successfully retrieved recent data for PR #{pr_number} in {repo_name}")

        return WebhookEventRawResults(
            updated_raw_results=[latest_pr], deleted_raw_results=[]
        )
