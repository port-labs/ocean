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
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from kinds import Kinds
from initialize_client import create_github_client
from authenticate import authenticate_github_webhook


class PullRequestWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "pull_request"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        pr = payload.get("pull_request", {})
        logger.info(f"Handling pull request event: {pr.get('title')}")

        repo = payload.get("repository", {})
        owner_login = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")
        client = create_github_client()
        pr_number = pr.get("number")

        updated_results = []

        if owner_login and repo_name and pr_number:
            logger.debug(f"Fetching updated PR data from GitHub for PR #{pr_number}")
            async for pr_page in client.fetch_single_github_resource(
                "pull_request", owner=owner_login, repo=repo_name, pull_number=pr_number
            ):
                if pr_page:
                    updated_results.extend(pr_page)
            if not updated_results:
                logger.warning(
                    "Could not fetch updated PR data. Using webhook payload."
                )
                updated_results.append(pr)
        else:
            logger.warning(
                "Missing owner, repo, or PR number in payload. Skipping fetch from GitHub."
            )
            updated_results.append(pr)

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=[]
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
