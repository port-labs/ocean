from typing import cast
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventPayload,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from github.helpers.utils import ObjectKind
from github.webhook.events import ISSUE_DELETE_EVENTS, ISSUE_EVENTS
from github.core.exporters.issue_exporter import RestIssueExporter
from github.core.options import SingleIssueOptions
from integration import GithubIssueConfig
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)


class IssueWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "issue" in payload and "number" in payload["issue"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "issues"
            and event.payload.get("action") in ISSUE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        action = payload["action"]
        issue = payload["issue"]
        repo_name = payload["repository"]["name"]
        issue_number = payload["issue"]["number"]

        logger.info(f"Processing issue event: {action} for {repo_name}/{issue_number}")

        config = cast(GithubIssueConfig, resource_config)

        if (
            action == "closed" and config.selector.state == "open"
        ) or action in ISSUE_DELETE_EVENTS:

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[issue],
            )

        exporter = RestIssueExporter(create_github_client())
        data_to_upsert = await exporter.get_resource(
            SingleIssueOptions(repo_name=repo_name, issue_number=issue_number)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
