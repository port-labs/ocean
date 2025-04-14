"""
pull_request_webhook_processor.py
---------------------------------
Processes GitHub pull request webhook events.
"""

import os
import json
import hmac
import hashlib
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, EventHeaders, WebhookEvent, WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from kinds import Kinds
from initialize_client import create_github_client
from dotenv import load_dotenv
from port_ocean.context.ocean import ocean
from authenticate import authenticate_github_webhook

load_dotenv()

class PullRequestWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "pull_request"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.PULL_REQUEST]

    async def handle_event(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        """
          Handle the GitHub pull_request webhook event.
          We attempt to fetch the full PR details from GitHub's API,
          in case the webhook payload is partial or outdated.
          """
        pr = payload.get("pull_request", {})
        logger.info(f"Handling pull request event: {pr.get('title')}")

        # Extracting repo & owner from the webhook
        repo = payload.get("repository", {})
        owner_login = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")

        client = create_github_client()

        # The GitHub webhook typically includes the PR number in 'number'
        pr_number = pr.get("number")

        # Attempt to fetch the full PR info from GitHub if we have enough data
        if owner_login and repo_name and pr_number:
            logger.debug(f"Fetching updated PR data from GitHub for PR #{pr_number}")
            async for  pr_data in client.fetch_resource("pull_request", owner=owner_login, repo=repo_name, pull_number=pr_number):
                if pr_data is not None:
                    logger.debug("Successfully updated the PR data from GitHub.")
                    pr = pr_data  # Overwrite the webhook data with the fresh data
                else:
                    logger.warning("Could not fetch updated PR data. Using webhook payload.")
        else:
            logger.warning("Missing owner, repo, or PR number in payload. Skipping fetch from GitHub.")

        return WebhookEventRawResults(
            updated_raw_results=[pr],
            deleted_raw_results=[]
        )


    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
