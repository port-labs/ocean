import fnmatch
from typing import Any, Dict, List, Optional, cast
import asyncio
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from azure_devops.client.azure_devops_client import AzureDevopsClient
from integration import AzureDevopsFileResourceConfig
from azure_devops.misc import Kind, extract_branch_name_from_ref
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.client.file_processing import parse_file_content
from azure_devops.webhooks.events import PushEvents


class FileWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.FILE]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(PushEvents(event_type))
        except ValueError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        matching_resource_config = cast(AzureDevopsFileResourceConfig, resource_config)
        selector = matching_resource_config.selector
        tracked_repository = selector.files.repos
        repository_name = payload["resource"]["repository"]["name"]
        if tracked_repository and (repository_name not in tracked_repository):
            logger.info(
                f"Skipping push event for repository {repository_name} because it is not in {tracked_repository}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = AzureDevopsClient.create_from_ocean_config()
        updates = payload["resource"]["refUpdates"]
        created, modified, deleted = await self._process_push_updates(
            matching_resource_config, payload, updates, client
        )
        return WebhookEventRawResults(
            updated_raw_results=created + modified,
            deleted_raw_results=deleted,
        )

    async def _process_push_updates(
        self,
        config: AzureDevopsFileResourceConfig,
        push_data: Dict[str, Any],
        updates: List[Dict[str, Any]],
        client: AzureDevopsClient,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        created_files: List[Dict[str, Any]] = []
        modified_files: List[Dict[str, Any]] = []
        deleted_files: List[Dict[str, Any]] = []
        tasks = []

        for update in updates:
            branch = extract_branch_name_from_ref(update["name"])
            default_branch = extract_branch_name_from_ref(
                push_data["resource"]["repository"]["defaultBranch"]
            )
            logger.info(f"Branch: {branch}, Default branch: {default_branch}")
            if branch != default_branch:
                logger.info("Skipping ref update for non-default branch")
                continue

            task = self._process_changed_files_for_ref(
                config, push_data, update, client
            )
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                created, modified, deleted = result
                created_files.extend(created)
                modified_files.extend(modified)
                deleted_files.extend(deleted)

        return created_files, modified_files, deleted_files

    async def _process_changed_files_for_ref(
        self,
        config: AzureDevopsFileResourceConfig,
        push_data: Dict[str, Any],
        update: Dict[str, Any],
        client: AzureDevopsClient,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        logger.info(f"Processing ref update: {update}")
        repo_id = push_data["resource"]["repository"]["id"]
        new_commit = update["newObjectId"]
        created, modified, deleted = await self._get_file_changes(
            repo_id, new_commit, config, client
        )

        return created, modified, deleted

    async def _get_file_changes(
        self,
        repo_id: str,
        commit_id: str,
        config: AzureDevopsFileResourceConfig,
        client: AzureDevopsClient,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        logger.info(f"Fetching file changes for commit {commit_id} in repo {repo_id}")
        created_files: List[Dict[str, Any]] = []
        modified_files: List[Dict[str, Any]] = []
        deleted_files: List[Dict[str, Any]] = []

        try:
            repo_info = await client.get_repository(repo_id)
            if not repo_info:
                logger.warning(f"Could not find repository with ID {repo_id}")
                return created_files, modified_files, deleted_files
            project_id = repo_info["project"]["id"]
            if not config.selector.files.path:
                return created_files, modified_files, deleted_files
            if isinstance(config.selector.files.path, str):
                path_to_track = [config.selector.files.path]
            else:
                path_to_track = config.selector.files.path

            response = await client.get_commit_changes(project_id, repo_id, commit_id)
            if not response:
                logger.warning(
                    f"No response when fetching changes for commit {commit_id}"
                )
                return created_files, modified_files, deleted_files

            changed_files = response.get("changes", []) if response else []

            for changed_file in changed_files:
                file_path = changed_file["item"]["path"]
                if not any(
                    fnmatch.fnmatch(file_path.strip("/"), pattern.strip("/"))
                    for pattern in path_to_track
                ):
                    logger.info(
                        f"Skipping file {file_path} as it doesn't match any patterns in {path_to_track}"
                    )
                    continue
                change_type = changed_file.get("changeType", "")
                logger.info(f"Change type: {change_type}")
                match change_type:
                    case "add":
                        file_entity = await self._build_file_entity(
                            repo_info, commit_id, changed_file, client
                        )
                        if file_entity:
                            created_files.append(file_entity)
                    case "delete":
                        deleted_files.append(
                            self._build_deleted_file_entity(repo_info, changed_file)
                        )
                    case _:
                        file_entity = await self._build_file_entity(
                            repo_info, commit_id, changed_file, client
                        )
                        if file_entity:
                            modified_files.append(file_entity)

        except Exception as e:
            logger.error(f"Error fetching file changes: {e}")

        return created_files, modified_files, deleted_files

    async def _build_file_entity(
        self,
        repo_info: Dict[str, Any],
        commit_id: str,
        changed_file: Dict[str, Any],
        client: AzureDevopsClient,
    ) -> Optional[Dict[str, Any]]:
        try:
            file_path = changed_file["item"]["path"]
            file_content = await client.get_file_by_commit(
                file_path, repo_info["id"], commit_id
            )
            if not file_content:
                logger.warning(f"No content found for file {file_path}")
                return None

            file_metadata = {
                **changed_file.get("item", {}),
                "size": len(file_content),
            }
            logger.debug(f"File metadata: {file_metadata}")

            parsed_content = await parse_file_content(file_content)

            return {
                "kind": Kind.FILE,
                "file": {
                    **file_metadata,
                    "content": {
                        "raw": file_content.decode("utf-8"),
                        "parsed": parsed_content,
                    },
                    "size": len(file_content),
                },
                "repo": repo_info,
            }

        except Exception as e:
            logger.error(f"Error processing file {changed_file['item']['path']}: {e}")
            return None

    def _build_deleted_file_entity(
        self, repo_info: Dict[str, Any], changed_file: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "kind": Kind.FILE,
            "file": {
                "path": changed_file["item"]["path"],
                "isDeleted": True,
            },
            "repo": repo_info,
        }
