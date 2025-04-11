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
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent, WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from kinds import Kinds
from initialize_client import create_github_client
from dotenv import load_dotenv

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
            pr_data = await client.fetch_pull_request(owner_login, repo_name, pr_number)

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


    async def authenticate(self, payload: dict, headers: dict) -> bool:
        secret = os.getenv("GITHUB_WEBHOOK_SECRET")
        if not secret:
            logger.error("GITHUB_WEBHOOK_SECRET is not set")
            return False
        received_signature = headers.get("x-hub-signature-256")
        if not received_signature:
            logger.error("Missing X-Hub-Signature-256 header")
            return False
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        computed_signature = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received_signature, computed_signature):
            logger.error("Signature verification failed for pull request event")
            return False
        return True

    async def validate_payload(self, payload: dict) -> bool:
        return True
