from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    EventHeaders,
    WebhookEvent,
    WebhookEventRawResults,
)
from kinds import Kinds
from initialize_client import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from authenticate import authenticate_github_webhook


class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "repository"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        logger.info(f"Received repository webhook payload: {payload.get("action")}")
        action = payload.get("action")
        repository = payload.get("repository", {})
        repo_name = repository.get("name")
        owner_info = repository.get("owner", {})
        owner_login = owner_info.get("login")
        client = create_github_client()

        logger.info(
            f"Handling repository event, action: {action} for repo: {repo_name}"
        )

        if action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[repository]
            )
        else:
            updated_results = []
            if owner_login and repo_name:
                logger.debug(
                    f"Fetching updated repo data from GitHub for owner={owner_login}, repo={repo_name}"
                )
                async for repo_page in client.fetch_single_github_resource(
                    "repository", owner=owner_login, repo=repo_name
                ):
                    if repo_page:
                        updated_results.extend(repo_page)
                if not updated_results:
                    logger.warning(
                        "Could not fetch updated repository data, using webhook payload."
                    )
                    updated_results.append(repository)
            else:
                logger.warning(
                    "No owner or repository name in payload, skipping GitHub fetch."
                )
                updated_results.append(repository)

            return WebhookEventRawResults(
                updated_raw_results=updated_results, deleted_raw_results=[]
            )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
