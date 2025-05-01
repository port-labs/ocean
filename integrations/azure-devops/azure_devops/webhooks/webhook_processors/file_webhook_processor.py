from typing import Any, Dict, List, Optional, cast
import asyncio
from loguru import logger
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from azure_devops.client.azure_devops_client import AzureDevopsClient
from integration import GitPortAppConfig
from azure_devops.misc import Kind, extract_branch_name_from_ref
from azure_devops.gitops.generate_entities import generate_entities_from_commit_id
from azure_devops.webhooks.webhook_processors._base_processor import (
    _AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.client.file_processing import parse_file_content
from azure_devops.webhooks.events import PushEvents


class FileWebhookProcessor(_AzureDevOpsBaseWebhookProcessor):
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
        config = cast(GitPortAppConfig, event.port_app_config)
        client = AzureDevopsClient.create_from_ocean_config()
        push_url = payload["resource"]["url"]
        push_params = {"includeRefUpdates": True}

        response = await client.send_request("GET", push_url, params=push_params)
        if not response:
            logger.warning(f"Couldn't get push data from url {push_url}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        push_data = response.json()
        updates = push_data["refUpdates"]
        created, modified, deleted = await self._process_push_updates(
            config, push_data, updates
        )

        return WebhookEventRawResults(
            updated_raw_results=created + modified,
            deleted_raw_results=deleted,
        )

    async def _process_push_updates(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        updates: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        created_files: List[Dict[str, Any]] = []
        modified_files: List[Dict[str, Any]] = []
        deleted_files: List[Dict[str, Any]] = []
        tasks = []

        for update in updates:
            branch = extract_branch_name_from_ref(update["name"])
            if config.use_default_branch:
                default_branch_with_ref = push_data["resource"]["repository"][
                    "defaultBranch"
                ]
                default_branch = extract_branch_name_from_ref(default_branch_with_ref)
            else:
                default_branch = config.branch

            if branch != default_branch:
                logger.info("Skipping ref update for non-default branch")
                continue

            task = self._process_changed_files_for_ref(config, push_data, update)
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
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        update: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        logger.info(f"Processing ref update: {update}")
        repo_id = update["repositoryId"]
        new_commit = update["newObjectId"]
        created, modified, deleted = await self._get_file_changes(repo_id, new_commit)

        new_entities = await generate_entities_from_commit_id(
            config.spec_path, repo_id, new_commit
        )
        logger.info(f"Got {len(new_entities)} new entities")

        all_created = created + [
            entity.dict() if hasattr(entity, "dict") else entity
            for entity in new_entities
        ]

        return (
            [item for item in all_created if isinstance(item, dict)],
            [item for item in modified if isinstance(item, dict)],
            [item for item in deleted if isinstance(item, dict)],
        )

    async def _get_file_changes(
        self, repo_id: str, commit_id: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        logger.info(f"Fetching file changes for commit {commit_id} in repo {repo_id}")
        created_files: List[Dict[str, Any]] = []
        modified_files: List[Dict[str, Any]] = []
        deleted_files: List[Dict[str, Any]] = []
        client = AzureDevopsClient.create_from_ocean_config()

        try:
            repo_info = await client.get_repository(repo_id)
            if not repo_info:
                logger.warning(f"Could not find repository with ID {repo_id}")
                return created_files, modified_files, deleted_files

            project_id = repo_info["project"]["id"]

            response = await client.get_commit_changes(project_id, repo_id, commit_id)
            if not response:
                logger.warning(
                    f"No response when fetching changes for commit {commit_id}"
                )
                return created_files, modified_files, deleted_files

            changed_files = response.get("changes", []) if response else []

            for changed_file in changed_files:
                change_type = changed_file.get("changeType", "")

                match change_type:
                    case "add":
                        file_entity = await self._build_file_entity(
                            repo_info, commit_id, changed_file
                        )
                        if file_entity:
                            created_files.append(file_entity)
                    case "delete":
                        deleted_files.append(
                            self._build_deleted_file_entity(repo_info, changed_file)
                        )
                    case _:
                        file_entity = await self._build_file_entity(
                            repo_info, commit_id, changed_file
                        )
                        if file_entity:
                            modified_files.append(file_entity)

        except Exception as e:
            logger.error(f"Error fetching file changes: {e}")

        return created_files, modified_files, deleted_files

    async def _build_file_entity(
        self, repo_info: Dict[str, Any], commit_id: str, changed_file: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            file_path = changed_file["item"]["path"]
            file_content = (
                await AzureDevopsClient.create_from_ocean_config().get_file_by_commit(
                    file_path, repo_info["id"], commit_id
                )
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
