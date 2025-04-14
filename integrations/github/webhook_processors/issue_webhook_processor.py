"""
issue_webhook_processor.py
--------------------------
Processes GitHub issue webhook events.
"""

import os
import json
import hmac
import hashlib
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, EventHeaders,WebhookEvent, WebhookEventRawResults
from kinds import Kinds
from initialize_client import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from dotenv import load_dotenv
from port_ocean.context.ocean import ocean
from authenticate import authenticate_github_webhook

load_dotenv()

class IssueWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # Process only if the event is 'issues' and the payload does not contain a "pull_request" key.
        if event.headers.get("x-github-event") != "issues":
            return False
        issue = event.payload.get("issue", {})
        return "pull_request" not in issue

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE]

    async def handle_event(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        """
         Handle a GitHub "issues" webhook event (opened, closed, edited, etc.).
         Enrich the issue data from GitHub's REST API if possible.
         """
        issue = payload.get("issue", {})
        logger.info(f"Handling issue event: {issue.get('title')}")

        # Extract the repo/owner from the webhook
        repo = payload.get("repository", {})
        owner_login = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")

        client = create_github_client()

        # The GitHub issue 'number' is needed to fetch the full issue
        issue_number = issue.get("number")

        # If we have the necessary info, fetch the latest issue data
        if owner_login and repo_name and issue_number is not None:
            logger.debug(f"Fetching updated issue data from GitHub for #{issue_number}")
            async for updated_issue in client.fetch_resource("pull_request", owner=owner_login, repo=repo_name, issue_number=issue_number):
                if updated_issue is not None:
                    issue = updated_issue  # Override the webhook payload with fresh data
                else:
                    logger.warning("Could not fetch updated issue data. Using webhook payload.")
        else:
            logger.warning("Missing owner, repo, or issue number in payload. Skipping GitHub fetch.")

        # Return the final (possibly enriched) issue for further processing
        return WebhookEventRawResults(
            updated_raw_results=[issue],
            deleted_raw_results=[]
        )


    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
