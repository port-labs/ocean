from typing import Any, Dict, List, Optional
import asyncio
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
)
from azure_devops.client.azure_devops_client import AzureDevopsClient
from integration import GitPortAppConfig
from azure_devops.misc import Kind, extract_branch_name_from_ref
from azure_devops.webhooks.webhook_processors._base_processor import (
    _AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.client.file_processing import parse_file_content
from azure_devops.webhooks.events import PushEvents
from azure_devops.gitops.generate_entities import generate_entities_from_commit_id


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
        config: GitPortAppConfig = event.port_app_config  # type: ignore
        updates = payload["resource"]["refUpdates"]
        # Process updates and generate entities
        processed_entities = await self._process_push_updates(config, payload, updates)

        return WebhookEventRawResults(
            updated_raw_results=processed_entities, deleted_raw_results=[]
        )

    async def _process_push_updates(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        updates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Process ref updates from push event and generate entities"""
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

            task = self._process_ref_update(config, push_data, update)
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                processed_entities.extend(result)

        return processed_entities

    async def _process_ref_update(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        update: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process a single ref update and generate entities"""
        logger.info(f"Processing ref update: {update}")
        repo_id = push_data["resource"]["repository"]["id"]
        old_commit = update["oldObjectId"]
        new_commit = update["newObjectId"]

        # Check if GitOps is being used (spec_path is configured)
        if hasattr(config, "spec_path") and config.spec_path:
            logger.warning(
                "GitOps usage detected via spec_path configuration. "
                "This is deprecated in favor of file-based processing."
            )

            # Generate entities from new commit
            new_entities = await generate_entities_from_commit_id(
                config.spec_path, repo_id, new_commit
            )
            logger.info(f"Got {len(new_entities)} new entities from GitOps")

            # Generate entities from old commit
            old_entities = await generate_entities_from_commit_id(
                config.spec_path, repo_id, old_commit
            )
            logger.info(f"Got {len(old_entities)} old entities from GitOps")

            # Calculate diff and update Port
            await ocean.update_diff(
                {"before": old_entities, "after": new_entities},
                UserAgentType.gitops,
            )
            # Convert Entity objects to dictionaries
            new_entities_dicts = [entity.dict() for entity in new_entities]
        else:
            new_entities_dicts = []

        # Process changed files in commit
        file_entities: List[Dict[str, Any]] = await self._sync_changed_files(
            repo_id, new_commit
        )

        return new_entities_dicts + file_entities

    async def _sync_changed_files(
        self, repo_id: str, commit_id: str
    ) -> List[Dict[str, Any]]:
        """Sync changed files from commit to Port"""
        logger.info(f"Fetching file changes for commit {commit_id} in repo {repo_id}")
        file_entities: List[Dict[str, Any]] = []
        client = AzureDevopsClient.create_from_ocean_config()

        try:
            repo_info = await client.get_repository(repo_id)
            if not repo_info:
                logger.warning(f"Could not find repository with ID {repo_id}")
                return file_entities

            project_id = repo_info["project"]["id"]
            url = f"{client._organization_base_url}/{project_id}/_apis/git/repositories/{repo_id}/commits/{commit_id}/changes"

            response = await client.send_request(
                "GET", url, params={"api-version": "7.1"}
            )
            if not response:
                logger.warning(
                    f"No response when fetching changes for commit {commit_id}"
                )
                return file_entities

            changed_files = response.json().get("changes", [])

            for changed_file in changed_files:
                file_entity = await self._process_changed_file(
                    repo_info, commit_id, changed_file
                )
                if file_entity:
                    file_entities.append(file_entity)

        except Exception as e:
            logger.error(f"Error fetching file changes: {e}")

        return file_entities

    async def _process_changed_file(
        self, repo_info: Dict[str, Any], commit_id: str, changed_file: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process a single changed file and create file entity"""
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
