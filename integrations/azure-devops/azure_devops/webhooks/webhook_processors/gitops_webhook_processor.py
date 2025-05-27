from typing import Any, Dict, List, cast
import asyncio
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event as port_ocean_event
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from integration import GitPortAppConfig
from azure_devops.misc import extract_branch_name_from_ref
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.webhooks.events import PushEvents
from azure_devops.gitops.generate_entities import generate_entities_from_commit_id
from azure_devops.client.azure_devops_client import AzureDevopsClient
import typing
from port_ocean.context.event import event as ocean_event


class GitopsWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        existing_config = self._get_any_existing_config()
        return [existing_config.kind]

    def _get_any_existing_config(self) -> ResourceConfig:
        resource_configs = typing.cast(
            GitPortAppConfig, ocean_event.port_app_config
        ).resources
        return resource_configs[0]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            config = cast(GitPortAppConfig, port_ocean_event.port_app_config)
            is_push_event = bool(PushEvents(event_type))
            has_spec_path = (
                hasattr(config, "spec_path") and config.spec_path is not None
            )
            is_port_yaml = isinstance(
                config.spec_path, str
            ) and config.spec_path.endswith("port.yml")

            return is_push_event and has_spec_path and is_port_yaml
        except ValueError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        config: GitPortAppConfig = cast(
            GitPortAppConfig, port_ocean_event.port_app_config
        )
        updates = payload["resource"]["refUpdates"]
        await self._process_push_updates(config, payload, updates)

        return WebhookEventRawResults(
            updated_raw_results=[], deleted_raw_results=[]
        )  # update happens in ocean.update_diff

    async def _process_push_updates(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        updates: List[Dict[str, Any]],
    ) -> None:
        """Process ref updates from push event and generate entities for GitOps"""
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
            await asyncio.gather(*tasks)

    async def _process_ref_update(
        self,
        config: GitPortAppConfig,
        push_data: Dict[str, Any],
        update: Dict[str, Any],
    ) -> None:
        """Process a single ref update and generate entities for GitOps"""
        try:
            logger.info(f"Processing GitOps ref update: {update}")
            repo_id = push_data["resource"]["repository"]["id"]
            old_commit = update["oldObjectId"]
            new_commit = update["newObjectId"]
            client = AzureDevopsClient.create_from_ocean_config()

            # Generate entities from new commit
            new_entities_dict = await generate_entities_from_commit_id(
                client, config.spec_path, new_commit, repo_id
            )
            logger.info(f"Got {len(new_entities_dict)} new entities from GitOps")

            # Generate entities from old commit
            old_entities_dict = await generate_entities_from_commit_id(
                client, config.spec_path, old_commit, repo_id
            )
            logger.info(f"Got {len(old_entities_dict)} old entities from GitOps")

            # Convert dictionaries to Entity objects
            new_entities = [Entity(**entity_dict) for entity_dict in new_entities_dict]
            old_entities = [Entity(**entity_dict) for entity_dict in old_entities_dict]

            # Calculate diff and update Port
            await ocean.update_diff(
                {"before": old_entities, "after": new_entities},
                UserAgentType.gitops,
            )
        except Exception as e:
            logger.error(f"Error processing ref update: {e}")
