from typing import cast
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEventRawResults,
    WebhookEvent,
)

from client.client import GithubRepositoryTypes
from integration import GithubRepositoryResourceConfig
from utils import ObjectKind, create_github_client


class GithubRepoWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        header = event.headers
        return header.get("x-github-event") == "repository"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPO]

    async def handle_event(
        self, event: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        config = cast(GithubRepositoryResourceConfig, resource_config)
        repo = event["repository"]
        github = create_github_client()
        match event["action"]:
            case "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[repo]
                )
            case _:
                repo = await github.get_repository(repo["full_name"])
                match config.selector.repo_type:
                    case GithubRepositoryTypes.ALL:
                        return WebhookEventRawResults(
                            updated_raw_results=[repo], deleted_raw_results=[]
                        )
                    case GithubRepositoryTypes.PRIVATE:
                        if repo["private"]:
                            return WebhookEventRawResults(
                                updated_raw_results=[repo],
                                deleted_raw_results=[],
                            )

                    case GithubRepositoryTypes.PUBLIC:
                        if not repo["private"]:
                            return WebhookEventRawResults(
                                updated_raw_results=[repo],
                                deleted_raw_results=[],
                            )
                    case GithubRepositoryTypes.FORKS:
                        if repo["fork"]:
                            return WebhookEventRawResults(
                                updated_raw_results=[repo],
                                deleted_raw_results=[],
                            )
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not payload.get("repository"):
            return False
        return True
