from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from gitlab.webhook.webhook_processors.push_path_changes import (
    resolve_push_path_changes,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from gitlab.helpers.utils import ObjectKind
from loguru import logger
from typing import Any, cast
import asyncio
import fnmatch
from integration import GitLabFilesResourceConfig


class FilePushWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FILE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project = payload["project"]
        project_id = project["id"]
        branch = self._get_branch_name(payload)
        repo_path = project["path_with_namespace"]
        if not self._is_default_branch_push(payload, "file"):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing push event for project {project_id} on branch {branch}"
        )

        config = cast(GitLabFilesResourceConfig, resource_config)
        selector = config.selector
        search_path = selector.files.path
        repos = selector.files.repos
        included_files = selector.included_files or []
        should_fetch_old_content = bool(resource_config.port.items_to_parse)

        # If repos is provided and doesn't include the event's repo, skip processing
        if repos and repo_path not in repos:
            logger.info(f"Repository {repo_path} not in configured repos; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        changed_files, removed_files, modified_files = await resolve_push_path_changes(
            self._gitlab_webhook_client, repo_path, payload
        )

        matching_files = sorted(
            [
                path
                for path in changed_files | removed_files
                if fnmatch.fnmatch(path, search_path)
            ]
        )

        if not matching_files:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        old_content_paths = set(removed_files)
        if should_fetch_old_content:
            old_content_paths |= modified_files

        changed_file_batch = [
            {"project_id": str(project_id), "path": file_path, "ref": payload["after"]}
            for file_path in matching_files
            if file_path in changed_files
        ]
        removed_file_batch = [
            {"project_id": str(project_id), "path": file_path, "ref": payload["before"]}
            for file_path in matching_files
            if file_path in old_content_paths
        ]

        updated_results, deleted_results = await asyncio.gather(
            self._fetch_enriched_files(
                changed_file_batch, project_id, selector.files.skip_parsing
            ),
            self._fetch_enriched_files(
                removed_file_batch, project_id, selector.files.skip_parsing
            ),
        )

        # Enrich updated file results with included files if configured
        if included_files and updated_results:
            from gitlab.enrichments.included_files import (
                IncludedFilesEnricher,
                FileIncludedFilesStrategy,
            )

            enricher = IncludedFilesEnricher(
                client=self._gitlab_webhook_client,
                strategy=FileIncludedFilesStrategy(included_files=included_files),
            )
            updated_results = await enricher.enrich_batch(updated_results)

        logger.info(
            f"Completed push event processing; updated {len(updated_results)} entities, deleted {len(deleted_results)} entities"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )

    async def _fetch_enriched_files(
        self,
        file_batch: list[dict[str, Any]],
        project_id: int | str,
        skip_parsing: bool,
    ) -> list[dict[str, Any]]:
        if not file_batch:
            return []
        processed_batch = await self._gitlab_webhook_client._process_file_batch(
            file_batch,
            context=f"project:{project_id}",
            skip_parsing=skip_parsing,
        )
        return await self._gitlab_webhook_client._enrich_files_with_repos(
            processed_batch
        )
