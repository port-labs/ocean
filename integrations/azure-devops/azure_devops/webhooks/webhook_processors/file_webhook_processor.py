from typing import Any, Dict, List, Optional, cast
import asyncio
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.clients.port.types import UserAgentType
from azure_devops.client.azure_devops_client import API_PARAMS, AzureDevopsClient
from azure_devops.misc import GitPortAppConfig, extract_branch_name_from_ref, Kind
from azure_devops.gitops.generate_entities import generate_entities_from_commit_id
from azure_devops.webhooks.webhook_processors._base_processor import (
    _AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.client.file_processing import parse_file_content
from azure_devops.webhooks.events import RepositoryEvents


class FileWebhookProcessor(_AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.FILE]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(RepositoryEvents(event_type))
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
        processed_entities = await self._process_push_updates(
            config, push_data, updates
        )

        return WebhookEventRawResults(
            updated_raw_results=processed_entities,
            deleted_raw_results=[],
        )

    async def _process_push_updates(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        updates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        processed_entities: List[Dict[str, Any]] = []
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

            task = self._handle_gitops_diff_for_ref(config, push_data, update)
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                processed_entities.extend(result)

        return processed_entities

    async def _handle_gitops_diff_for_ref(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        update: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        logger.info(f"Processing ref update: {update}")
        repo_id = update["repositoryId"]
        old_commit = update["oldObjectId"]
        new_commit = update["newObjectId"]

        new_entities = await generate_entities_from_commit_id(
            config.spec_path, repo_id, new_commit
        )
        logger.info(f"Got {len(new_entities)} new entities")

        old_entities = await generate_entities_from_commit_id(
            config.spec_path, repo_id, old_commit
        )
        logger.info(f"Got {len(old_entities)} old entities")

        await ocean.update_diff(
            {"before": old_entities, "after": new_entities},
            UserAgentType.gitops,
        )

        file_entities = await self._sync_changed_files(repo_id, new_commit)

        all_entities = new_entities + file_entities
        return [
            entity.dict() if hasattr(entity, "dict") else entity
            for entity in all_entities
        ]

    async def _sync_changed_files(
        self, repo_id: str, commit_id: str
    ) -> List[Dict[str, Any]]:
        logger.info(f"Fetching file changes for commit {commit_id} in repo {repo_id}")
        file_entities: List[Dict[str, Any]] = []

        try:
            repo_info = (
                await AzureDevopsClient.create_from_ocean_config().get_repository(
                    repo_id
                )
            )
            if not repo_info:
                logger.warning(f"Could not find repository with ID {repo_id}")
                return file_entities

            project_id = repo_info["project"]["id"]
            url = f"{AzureDevopsClient.create_from_ocean_config()._organization_base_url}/{project_id}/_apis/git/repositories/{repo_id}/commits/{commit_id}/changes"

            response = await AzureDevopsClient.create_from_ocean_config().send_request(
                "GET", url, params=API_PARAMS
            )
            if not response:
                logger.warning(
                    f"No response when fetching changes for commit {commit_id}"
                )
                return file_entities

            changed_files = response.json().get("changes", [])

            for changed_file in changed_files:
                file_entity = await self._build_file_entity_from_commit(
                    repo_info, commit_id, changed_file
                )
                if file_entity:
                    file_entities.append(file_entity)

        except Exception as e:
            logger.error(f"Error fetching file changes: {e}")

        return file_entities

    async def _build_file_entity_from_commit(
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
