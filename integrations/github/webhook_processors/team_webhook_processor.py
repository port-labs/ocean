"""
team_webhook_processor.py
-------------------------
Processes GitHub team webhook events.
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
from authenticate import authenticate_github_webhook

load_dotenv()

class TeamWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "team"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.TEAM]

    async def handle_event(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        """
          Handle incoming webhook for GitHub team events.
          Enrich the team data by calling GitHub to get the full team details.
          """
        team_info = payload.get("team", {})
        team_name = team_info.get("name")
        team_slug = team_info.get("slug")

        client = create_github_client()

        logger.info(f"Handling team event: {team_name}")

        # Grab org info from the payload
        org_info = payload.get("organization", {})
        org = org_info.get("login")

        # If we have enough data, fetch the full team details from GitHub
        if org and team_slug:
            logger.debug(f"Fetching updated team data from GitHub for team slug={team_slug}")
            async for team_data in client.fetch_resource("teams", org=org, team_slug=team_slug):
                if team_data:
                    team_info = team_data  # Override the webhook's partial data
                else:
                    logger.warning("Could not retrieve updated team data from GitHub. Using webhook payload only.")
        else:
            logger.warning("Missing org or team slug in webhook payload. Skipping GitHub team fetch.")

        return WebhookEventRawResults(
            updated_raw_results=[team_info],
            deleted_raw_results=[]
        )


    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
