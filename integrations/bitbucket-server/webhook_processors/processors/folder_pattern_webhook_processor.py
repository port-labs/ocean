from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Iterable, Any

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
    # optional:
    "pr:declined",
    "pr:modified",
}


class FolderPatternWebhookProcessor(BaseWebhookProcessorMixin):
    """
    On relevant repo/PR events, re-hydrates the current set of matching folders
    for *all patterns* configured under resource.selector.folders for the
    affected repo (no commit/compare usage).
    """

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        key = event.payload.get("eventKey")
        return key in FOLDER_PATTERN_RELEVANT_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    # ---- helpers ----

    def _extract_repo_locator(
        self, payload: EventPayload
    ) -> Tuple[Optional[str], Optional[str]]:
        repo = payload.get("repository") or payload.get("new") or {}
        project = repo.get("project") or {}
        project_key = project.get("key") or payload.get("project", {}).get("key")
        repo_slug = repo.get("slug") or payload.get("slug")
        if not project_key or not repo_slug:
            logger.warning(
                f"[FolderPatternWebhook] Could not extract repo locator from payload: {payload}"
            )
        return project_key, repo_slug

    def _iter_folder_patterns_from_resource(
        self, resource: ResourceConfig
    ) -> Iterable[BitbucketServerFolderPattern]:
        """
        Returns an iterator over BitbucketServerFolderPattern objects from resource.selector.folders.
        Handles single-or-list cases safely.
        """
        selector = getattr(resource, "selector", None)
        if not selector:
            logger.warning("[FolderPatternWebhook] Resource has no selector")
            return []

        folders_attr = getattr(selector, "folders", None)
        if not folders_attr:
            logger.warning(
                "[FolderPatternWebhook] selector.folders is empty or missing"
            )
            return []

        # Could be a single pattern or a list
        if isinstance(folders_attr, list):
            return [p for p in folders_attr if p]
        return [folders_attr]

    def _pattern_matches_repo(
        self, pattern: BitbucketServerFolderPattern, project_key: str, repo_slug: str
    ) -> bool:
        if pattern.project_key not in (project_key, "*"):
            return False
        if (
            pattern.repos
            and repo_slug not in pattern.repos
            and "*" not in pattern.repos
        ):
            return False
        return True

    # ---- main ----

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        project_key, repo_slug = self._extract_repo_locator(payload)
        if not project_key or not repo_slug:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        patterns = list(self._iter_folder_patterns_from_resource(resource))
        if not patterns:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        # Fetch repo once; reused for all patterns
        repo_obj = await self._client.get_single_repository(project_key, repo_slug) or {
            "slug": repo_slug,
            "project": {"key": project_key},
        }
        repo_info = (repo_obj, project_key)

        updated: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str]] = (
            set()
        )  # (project_key, repo_slug, folder_path)

        for pattern in patterns:
            if not self._pattern_matches_repo(pattern, project_key, repo_slug):
                continue

            try:
                matches = await process_repository_folders(
                    self._client, repo_info, pattern
                )
            except Exception as e:
                logger.error(
                    f"[FolderPatternWebhook] Failed processing repo {project_key}/{repo_slug} for pattern {getattr(pattern, 'path', '')}: {e}"
                )
                continue

            # De-duplicate across patterns by (project, repo, folder.path)
            for m in matches:
                folder = m.get("folder") or {}
                folder_path = folder.get("path", "")
                key = (project_key, repo_slug, folder_path)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                updated.append(m)

        return WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=[],  # full-refresh model (no commit-based deletes)
        )
