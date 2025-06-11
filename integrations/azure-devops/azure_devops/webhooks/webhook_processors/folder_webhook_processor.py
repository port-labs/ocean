from typing import List, cast
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from azure_devops.misc import (
    Kind,
    extract_branch_name_from_ref,
    AzureDevopsFolderResourceConfig,
)
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.webhooks.events import PushEvents
from azure_devops.client.azure_devops_client import AzureDevopsClient
import fnmatch


class FolderWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.FOLDER]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            is_push_event = bool(PushEvents(event_type))
            return is_push_event
        except ValueError:
            return False

    def _matches_folder_pattern(
        self, folder_path: str, folder_patterns: List[str]
    ) -> bool:
        """Check if a folder path matches any of the configured patterns."""
        folder_path = folder_path.strip("/")
        for pattern in folder_patterns:
            pattern = pattern.strip("/")
            if folder_path.count("/") == pattern.count("/") and fnmatch.fnmatch(
                folder_path, pattern
            ):
                return True
        return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        logger.info("Processing folder webhook event")
        client = AzureDevopsClient.create_from_ocean_config()
        repository = payload["resource"]["repository"]
        repo_id = repository["id"]
        project_id = repository["project"]["id"]
        updates = payload["resource"]["refUpdates"]

        folder_config = cast(AzureDevopsFolderResourceConfig, resource_config)
        folder_patterns = [pattern.path for pattern in folder_config.selector.folders]

        repo_name = repository["name"]
        configured_repos = {
            repo_mapping.name
            for pattern in folder_config.selector.folders
            for repo_mapping in pattern.repos
        }

        if repo_name not in configured_repos:
            logger.info(
                f"Skipping folder event for repository {repo_name} as it's not in configured repos"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        created_folders = []
        modified_folders = []
        deleted_folders = []

        for update in updates:
            new_commit = update["newObjectId"]

            changes = await client.get_commit_changes(project_id, repo_id, new_commit)

            folder_changes = [
                change
                for change in changes.get("changes", [])
                if change.get("item", {}).get("isFolder", False)
            ]

            if folder_changes:
                logger.info(f"Found {len(folder_changes)} folder changes")

                for change in folder_changes:
                    item = change["item"]
                    folder_path = item["path"]

                    if not self._matches_folder_pattern(folder_path, folder_patterns):
                        logger.info(
                            f"Skipping folder {folder_path} as it doesn't match any configured patterns"
                        )
                        continue

                    change_type = change["changeType"]

                    folder_entity = {
                        "kind": Kind.FOLDER,
                        "objectId": item["objectId"],
                        "path": item["path"],
                        "__repository": repository,
                        "__branch": extract_branch_name_from_ref(update["name"]),
                        "__pattern": item["path"],
                    }

                    match change_type:
                        case "add":
                            created_folders.append(folder_entity)
                        case "delete":
                            deleted_folders.append(folder_entity)
                        case _:
                            modified_folders.append(folder_entity)

        return WebhookEventRawResults(
            updated_raw_results=created_folders + modified_folders,
            deleted_raw_results=deleted_folders,
        )
