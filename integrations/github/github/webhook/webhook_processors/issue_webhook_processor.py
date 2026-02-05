from typing import cast, Any
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventPayload,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from github.helpers.utils import (
    ObjectKind,
    enrich_with_organization,
    enrich_with_repository,
)
from github.webhook.events import ISSUE_DELETE_EVENTS, ISSUE_EVENTS
from github.core.exporters.issue_exporter import RestIssueExporter
from github.core.options import SingleIssueOptions
from integration import GithubIssueConfig, GithubIssueSelector
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from github.helpers.utils import issue_matches_labels


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
        repo = payload["repository"]
        repo_name = repo["name"]
        issue_number = payload["issue"]["number"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubIssueConfig, resource_config)

        logger.info(
            f"Processing issue event: {action} for {repo_name}/{issue_number} from {organization}"
        )

        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not self._check_labels_filter(config.selector, issue):
            logger.info(
                f"Issue {repo_name}/{issue_number} filtered out by selector criteria"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if (
            action == "closed" and config.selector.state == "open"
        ) or action in ISSUE_DELETE_EVENTS:
            data_to_delete = enrich_with_organization(
                enrich_with_repository(issue, repo_name, repo=repo), organization
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[data_to_delete],
            )
        exporter = RestIssueExporter(create_github_client())
        data_to_upsert = await exporter.get_resource(
            SingleIssueOptions(
                organization=organization,
                repo_name=repo_name,
                issue_number=issue_number,
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    def _check_labels_filter(
        self, selector: GithubIssueSelector, issue: dict[str, Any]
    ) -> bool:
        """Check if issue labels match selector labels filter."""
        return issue_matches_labels(issue["labels"], selector.labels)
