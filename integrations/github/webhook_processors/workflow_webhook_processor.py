"""
workflow_run_webhook_processor.py
---------------------------------
Processes GitHub workflow run webhook events.
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

class WorkflowRunWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "workflow_run"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.WORKFLOW]

    async def handle_event(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        workflow_run = payload.get("workflow_run", {})
        run_name = workflow_run.get("name", "N/A")
        logger.info(f"Handling workflow run event: {run_name}")

        client = create_github_client()

        # Extract repository and run info from the webhook
        repo = payload.get("repository", {})
        repo_owner = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")
        run_id = workflow_run.get("id")

        # If we have enough info, fetch the latest run details from GitHub
        if repo_owner and repo_name and run_id:
            logger.debug(f"Fetching updated run data from GitHub for run_id={run_id}")
            run_data = await client.fetch_workflow_run(repo_owner, repo_name, str(run_id))

            if run_data:
                workflow_run = run_data  # Replace the webhook payload with the freshly fetched data
            else:
                logger.warning("Could not retrieve updated run data from GitHub, using webhook payload only.")
        else:
            logger.warning("Missing owner, repo, or run_id in webhook payload. Skipping refresh from GitHub.")

        # Return the final workflow run data for further processing
        return WebhookEventRawResults(
            updated_raw_results=[workflow_run],
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
            logger.error("Signature verification failed for workflow_run event")
            return False
        return True

    async def validate_payload(self, payload: dict) -> bool:
        return True
