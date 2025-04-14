"""
repository_webhook_processor.py
---------------------------------
Processes GitHub repository webhook events.
"""

import os
import json
import hmac
import hashlib
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (AbstractWebhookProcessor,)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, EventHeaders,WebhookEvent, WebhookEventRawResults
from kinds import Kinds
from initialize_client import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from dotenv import load_dotenv
from port_ocean.context.ocean import ocean
from authenticate import authenticate_github_webhook

load_dotenv()


class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # Process only if the GitHub event header is "repository"
        return event.headers.get("x-github-event") == "repository"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        # This processor produces data for the repository resource
        return [Kinds.REPOSITORY]

    async def handle_event(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        """
            Handle incoming GitHub webhook for repository events (create, delete, rename, etc.).
            We look up the repository in GitHub if not deleted, to ensure we have current data.
            """
        logger.info(f"Received repository webhook payload: {payload}")

        action = payload.get("action")
        repository = payload.get("repository", {})
        repo_name = repository.get("name")
        owner_info = repository.get("owner", {})
        owner_login = owner_info.get("login")

        client = create_github_client()

        logger.info(f"Handling repository event, action: {action} for repo: {repo_name}")

        # If the repository was deleted, return it under "deleted" results.
        if action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[repository]
            )
        else:
            # If the repo is not deleted, try to enrich the data from GitHub
            if owner_login and repo_name:
                logger.debug(f"Fetching updated repo data from GitHub for owner={owner_login}, repo={repo_name}")
                async for  repo_data in client.fetch_resource("repository", owner = owner_login, repo=repo_name):
                    if repo_data:
                        repository = repo_data  # Overwrite with the fresh data
                    else:
                        logger.warning("Could not fetch updated repository data, using webhook payload.")
            else:
                logger.warning("No owner or repository name in payload, skipping GitHub fetch.")

            # Return in updated_raw_results
            return WebhookEventRawResults(
                updated_raw_results=[repository],
                deleted_raw_results=[]
            )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        # Additional validation logic may be added here.
        return True
