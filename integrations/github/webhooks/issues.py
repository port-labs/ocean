from typing import cast
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from client.client import GithubRepositoryTypes
from integration import GithubIssueResourceConfig
from utils import PortGithubResources


class GithubIssueWebhookHandler(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        header = event.headers
        print(header)
        return header.get("X_GitHub_Event") == "issues"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [PortGithubResources.ISSUE]

    async def handle_event(
        self, event: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        match event.get("action"):
            case "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[event["issue"]]
                )
            case _:
                config = cast(GithubIssueResourceConfig, resource_config)
                issue_repo = event["repository"]
                match config.selector.repo_type:
                    case GithubRepositoryTypes.ALL:
                        return WebhookEventRawResults(
                            updated_raw_results=[event["issue"]], deleted_raw_results=[]
                        )
                    case GithubRepositoryTypes.PRIVATE:
                        if issue_repo["private"]:
                            return WebhookEventRawResults(
                                updated_raw_results=[event["issue"]],
                                deleted_raw_results=[],
                            )
                    case GithubRepositoryTypes.PUBLIC:
                        if not issue_repo["private"]:
                            return WebhookEventRawResults(
                                updated_raw_results=[event["issue"]],
                                deleted_raw_results=[],
                            )
                    case GithubRepositoryTypes.FORKS:
                        if issue_repo["fork"]:
                            return WebhookEventRawResults(
                                updated_raw_results=[event["issue"]],
                                deleted_raw_results=[],
                            )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
