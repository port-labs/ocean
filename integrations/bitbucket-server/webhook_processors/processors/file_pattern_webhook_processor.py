from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import BitbucketServerFilePattern, ObjectKind
from webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)

# Reuse your existing per-repo file processing helper
from helpers.file import process_repository_files


# Choose the events you want to react to; you can also reuse REPO_WEBHOOK_EVENTS if you like.
FILE_PATTERN_RELEVANT_EVENTS = {
    # Repo general changes (push/branch changes)
    "repo:refs_changed",
    "repo:modified",
    # PR merges often change default branches
    "pr:merged",
    # Optional:
    "pr:declined",
    "pr:modified",
}


class FilePatternWebhookProcessor(BaseWebhookProcessorMixin):
    """
    On relevant repo/PR events, re-hydrates the current set of matching files
    in the affected repo (no commit/compare usage).
    Returns the same shape as helpers.file.process_repository_files yields.
    """

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        key = event.payload.get("eventKey")
        return key in FILE_PATTERN_RELEVANT_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FILE]

    # ---- helpers ----

    def _extract_repo_locator(self, payload: EventPayload) -> Tuple[Optional[str], Optional[str]]:
        repo = payload.get("repository") or payload.get("new") or {}
        project = repo.get("project") or {}
        project_key = project.get("key") or payload.get("project", {}).get("key")
        repo_slug = repo.get("slug") or payload.get("slug")
        if not project_key or not repo_slug:
            logger.warning(f"[FilePatternWebhook] Could not extract repo locator from payload: {payload}")
        return project_key, repo_slug

    def _build_file_pattern_from_resource(
    self, resource: ResourceConfig
    ) -> Optional[BitbucketServerFilePattern]:
        """
        Build a BitbucketServerFilePattern from the resource's selector.
        resource.selector is a BitbucketServerFileSelector; the actual pattern
        is found on its `files` attribute.
        """
        try:
            selector = getattr(resource, "selector", None)
            if not selector:
                logger.warning("[FilePatternWebhook] Resource has no selector")
                return None

            files_attr = getattr(selector, "files", None)
            if not files_attr:
                logger.warning("[FilePatternWebhook] selector.files is empty or missing")
                return None

            # selector.files may be a single BitbucketServerFilePattern or a list of them.
            if isinstance(files_attr, list):
                # If multiple are configured, pick the first (or extend the processor to iterate them).
                pattern = files_attr[0] if files_attr else None
            else:
                pattern = files_attr

            if pattern is None:
                logger.warning("[FilePatternWebhook] No usable file pattern found in selector.files")
                return None

            # Optional: quick sanity checks to avoid surprises at runtime
            if not getattr(pattern, "project_key", None):
                logger.warning("[FilePatternWebhook] Pattern missing project_key")
            if not getattr(pattern, "filenames", None):
                logger.warning("[FilePatternWebhook] Pattern has no filenames")

            return pattern

        except Exception as e:
            logger.error(
                f"[FilePatternWebhook] Failed to build BitbucketServerFilePattern from resource.selector.files: {e}"
            )
            return None

    # ---- main ----

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        project_key, repo_slug = self._extract_repo_locator(payload)
        if not project_key or not repo_slug:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        pattern = self._build_file_pattern_from_resource(resource)
        if not pattern:
            logger.warning("[FilePatternWebhook] No usable file pattern in resource; skipping.")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Respect repo filter if present
        if pattern.repos and repo_slug not in pattern.repos and "*" not in pattern.repos:
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Respect project filter if present
        if pattern.project_key not in (project_key, "*"):
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Hydrate the repo object (optional, used by helper result)
        repo_obj = await self._client.get_single_repository(project_key, repo_slug) or {
            "slug": repo_slug,
            "project": {"key": project_key},
        }

        # Run your existing per-repo file pipeline (no commits, just current state)
        updated: List[Dict[str, Any]] = []
        async for batch in process_repository_files(self._client, repo_obj, pattern):
            # process_repository_files yields lists (batches) of file results; we flatten for WebhookEventRawResults
            updated.extend(batch)

        return WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=[],  # no deletes (full refresh model)
        )
