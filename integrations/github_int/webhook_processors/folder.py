# integrations/github/webhook_processors/folder.py
from typing import List
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults, EventPayload, EventHeaders
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import cast

from github.client import GitHubClient
from integration import FolderResourceConfig
from utils import ObjectKind

from initialize_client import create_github_client as create_client


class FolderWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("X-GitHub-Event") == "push"

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return [ObjectKind.FOLDER]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        signature = headers.get("X-Hub-Signature-256")
        if signature:
            return create_client().verify_webhook_signature(payload, signature)
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "ref" in payload and "commits" in payload and "repository" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        selector = cast(FolderResourceConfig, resource_config).selector
        client = create_client()
        repo = payload["repository"]["full_name"]
        repo_id = payload["repository"]["id"]
        default_branch = payload["repository"]["default_branch"]
        if not payload["ref"].startswith(f"refs/heads/{default_branch}"):
            logger.info("Push not on default branch; skipping folders.")
            return WebhookEventRawResults([], [])

        # On push, re-fetch all folders for this repo (or filter by changed paths if needed)
        # For efficiency, check commits for added/modified/removed paths that are folders
        updated_folders = []
        deleted_folders = []
        changed_paths = set()
        for commit in payload.get("commits", []):
            changed_paths.update(commit.get("added", []))
            changed_paths.update(commit.get("modified", []))
            for path in commit.get("removed", []):
                if path.endswith('/'):  # Assume trailing / indicates folder removal
                    deleted_folders.append({"repository_id": repo_id, "path": path.rstrip('/')})

        # Fetch updated folders based on changed paths (prefix match for subfolders)
        if changed_paths:
            # Re-fetch all folders to detect changes (simple approach; optimize by fetching only affected tree if needed)
            async for batch in client.get_folders(repo, repo_id, default_branch, selector.paths):
                # Filter to only include paths that match changes or are subpaths
                affected_batch = [f for f in batch if any(changed.startswith(f["path"]) or f["path"].startswith(changed) for changed in changed_paths)]
                updated_folders.extend(affected_batch)
        else:
            # Full re-fetch if no specific changes
            async for batch in client.get_folders(repo, repo_id, default_branch, selector.paths):
                updated_folders.extend(batch)

        logger.info(f"Processed {len(updated_folders)} updated and {len(deleted_folders)} deleted folders from {repo}")
        return WebhookEventRawResults(updated_raw_results=updated_folders, deleted_raw_results=deleted_folders)