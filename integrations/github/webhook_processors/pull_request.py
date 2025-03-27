from loguru import logger
from consts import PULL_REQUEST_DELETE_EVENTS, PULL_REQUEST_UPSERT_EVENTS
from helpers.utils import ObjectKind
from client import GitHubClient
from webhook_processors.abstract import GitHubAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class PullRequestWebhookProcessor(GitHubAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        return (
            event.headers.get("X-GitHub-Event") == "pull_request"
            and event_type in PULL_REQUEST_UPSERT_EVENTS + PULL_REQUEST_DELETE_EVENTS
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
            logger.info(f"Pull request #{pr.get('number')} was deleted in {repo_name}")

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[pr],
            )

        client = GitHubClient.from_ocean_config()
        latest_pr = await client.get_single_resource(
            ObjectKind.PULL_REQUEST, f"{repo_name}/{pr_number}"
        )

        return WebhookEventRawResults(
            updated_raw_results=[latest_pr], deleted_raw_results=[]
        )
