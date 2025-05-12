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


class IssueWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        if event.headers.get("x-github-event") != "issues":
            return False
        issue = event.payload.get("issue", {})
        return "pull_request" not in issue

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue = payload.get("issue", {})
        logger.info(f"Handling issue event: {issue.get('title')}")

        repo = payload.get("repository", {})
        owner_login = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")
        client = create_github_client()
        issue_number = issue.get("number")

        updated_results = []

        if owner_login and repo_name and issue_number is not None:
            logger.debug(f"Fetching updated issue data from GitHub for #{issue_number}")
            async for updated_page in client.fetch_single_github_resource(
                "issue", owner=owner_login, repo=repo_name, issue_number=issue_number
            ):

                if updated_page:
                    updated_results.extend(updated_page)
            if not updated_results:
                logger.warning(
                    "Could not fetch updated issue data. Using webhook payload."
                )
                updated_results.append(issue)
        else:
            logger.warning(
                "Missing owner, repo, or issue number in payload. Skipping GitHub fetch."
            )
            updated_results.append(issue)

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=[]
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
