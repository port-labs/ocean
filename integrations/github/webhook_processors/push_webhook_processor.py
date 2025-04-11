"""
push_webhook_processor.py
-------------------------
Processes GitHub push webhook events.
"""

import os
import json
import hmac
import hashlib
from typing import List

from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload,WebhookEvent, WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from ..kinds import Kinds
from ..initialize_client import create_github_client
from dotenv import load_dotenv
from port_ocean.context.ocean import ocean

load_dotenv()

class PushWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "push"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.FILE]

    async def handle_event(self, payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults:
        logger.info("Handling push event")

        # Extract basic repo info from the webhook
        repo = payload.get("repository", {})
        repo_name = repo.get("name")
        owner_login = repo.get("owner", {}).get("login")
        repo_html_url = repo.get("html_url")

        client = create_github_client()

        # 'entities' will hold your final "file" items for updated_raw_results
        entities: List[dict] = []

        # Get commits from the payload
        commits = payload.get("commits", [])
        logger.info(f"Processing {len(commits)} commits")

        if not commits:
            # Fallback to head_commit if commits array is empty
            head_commit = payload.get("head_commit")
            if head_commit:
                commits = [head_commit]
                logger.info("Using head_commit instead of empty commits array")

        # Process each commit
        for commit in commits:
            commit_sha = commit.get("id")
            logger.info(f"Processing commit {commit_sha}")

            enriched_commit = None
            # Attempt to enrich the commit data by fetching from GitHub
            try:
                if owner_login and repo_name and commit_sha:
                    enriched_commit = await client.fetch_commit(owner_login, repo_name, commit_sha)
                    if enriched_commit is not None:
                        logger.info(f"Successfully fetched enriched commit data for {commit_sha}")
                    else:
                        logger.warning(
                            f"Using partial commit data from webhook for {commit_sha}, could not fetch from GitHub.")
                else:
                    logger.warning("Missing owner, repo, or commit ID, skipping GitHub commit fetch.")
            except Exception as e:
                logger.error(f"Error fetching commit data: {str(e)}")
                # Continue with the webhook data we have

            # If we have enriched data from the API, use that
            if enriched_commit is not None:
                # Handle GitHub API response format
                # In the API response, files are in a 'files' array with 'status' field
                files = enriched_commit.get("files", [])
                for file_data in files:
                    status = file_data.get("status")
                    filename = file_data.get("filename")

                    if not filename:
                        continue

                    # Map status to action
                    action = {
                        "added": "added",
                        "modified": "modified",
                        "removed": "removed",
                        "renamed": "modified",  # Treating renamed as modified
                        "changed": "modified",  # Treating changed as modified
                        "copied": "added"  # Treating copied as added
                    }.get(status, "modified")  # Default to modified if unknown status

                    entities.append({
                        "id": f"{commit_sha}-{filename}",
                        "action": action,
                        "repo": repo_name,
                        "htmlUrl": file_data.get("blob_url") or f"{repo_html_url}/blob/{commit_sha}/{filename}",
                        "name": filename.split("/")[-1],
                        "path": filename,
                        "type": "file"
                    })
                    logger.debug(f"Added entity for {action} file from API: {filename}")
            else:
                # Process webhook format - has added, modified, removed arrays
                for file_list, action in [
                    (commit.get("added", []), "added"),
                    (commit.get("modified", []), "modified"),
                    (commit.get("removed", []), "removed"),
                ]:
                    for filename in file_list:
                        entities.append({
                            "id": f"{commit_sha}-{filename}",
                            "action": action,
                            "repo": repo_name,
                            "htmlUrl": f"{repo_html_url}/blob/{commit_sha}/{filename}" if repo_html_url else None,
                            "name": filename.split("/")[-1],
                            "path": filename,
                            "type": "file"
                        })
                        logger.debug(f"Added entity for {action} file from webhook: {filename}")

        # Log the number of entities found
        logger.info(f"Found {len(entities)} file entities across all commits")

        # Return the WebhookEventRawResults object with the collected entities
        return WebhookEventRawResults(updated_raw_results=entities, deleted_raw_results=[])

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        secret = ocean.integration_config.get("github_webhook_secret")
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
            logger.error("Signature verification failed for push event")
            return False
        return True

    async def validate_payload(self, payload: dict) -> bool:
        return True
