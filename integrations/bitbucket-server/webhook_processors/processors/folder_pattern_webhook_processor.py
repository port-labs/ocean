from __future__ import annotations

from typing import Optional, Tuple, Dict, Any, List

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import BitbucketServerFolderPattern, ObjectKind
from webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)

# Reuse your existing per-repo folder processing helper
from helpers.folder import process_repository_folders


FOLDER_PATTERN_RELEVANT_EVENTS = {
    "repo:refs_changed",
    "repo:modified",
    "pr:merged",
    # Optional:
    "pr:declined",
    "pr:modified",
}


class FolderPatternWebhookProcessor(BaseWebhookProcessorMixin):
    """
    On relevant repo/PR events, re-hydrates the current set of matching folders
    in the affected repo (no commit/compare usage).
    Returns the same shape as helpers.folder.process_repository_folders returns.
    """

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        key = event.payload.get("eventKey")
        return key in FOLDER_PATTERN_RELEVANT_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    # ---- helpers ----

    def _extract_repo_locator(self, payload: EventPayload) -> Tuple[Optional[str], Optional[str]]:
        repo = payload.get("repository") or payload.get("new") or {}
        project = repo.get("project") or {}
        project_key = project.get("key") or payload.get("project", {}).get("key")
        repo_slug = repo.get("slug") or payload.get("slug")
        if not project_key or not repo_slug:
            logger.warning(f"[FolderPatternWebhook] Could not extract repo locator from payload: {payload}")
        return project_key, repo_slug

    def _build_folder_pattern_from_resource(self, resource: ResourceConfig) -> Optional[BitbucketServerFolderPattern]:
        try:
            cfg = resource.config or {}
            return BitbucketServerFolderPattern(**cfg)
        except Exception as e:
            logger.error(f"[FolderPatternWebhook] Failed to build BitbucketServerFolderPattern from resource config: {e}")
            return None

    # ---- main ----

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        project_key, repo_slug = self._extract_repo_locator(payload)
        if not project_key or not repo_slug:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        pattern = self._build_folder_pattern_from_resource(resource)
        if not pattern:
            logger.warning("[FolderPatternWebhook] No usable folder pattern in resource; skipping.")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Respect repo filter if present
        if pattern.repos and repo_slug not in pattern.repos and "*" not in pattern.repos:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Respect project filter if present
        if pattern.project_key not in (project_key, "*"):
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Hydrate the repo object (for folder helper signature)
        repo_obj = await self._client.get_single_repository(project_key, repo_slug) or {
            "slug": repo_slug,
            "project": {"key": project_key},
        }
        repo_info = (repo_obj, project_key)

        # Run your existing per-repo folder pipeline (no commits, just current state)
        updated = await process_repository_folders(self._client, repo_info, pattern)

        return WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=[],  # no deletes (full refresh model)
        )
