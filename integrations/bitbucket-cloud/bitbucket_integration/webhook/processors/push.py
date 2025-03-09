from typing import cast, List, Any
from loguru import logger
from integration import BitbucketAppConfig
from bitbucket_integration.gitops.entity_generator import get_commit_hash_from_payload
from bitbucket_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from bitbucket_integration.webhook.processors._base import _BaseWebhookProcessorConfig
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_integration.gitops.commit_processor import process_diff_stats


class PushWebhookProcessor(_BaseWebhookProcessorConfig):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        config = cast(BitbucketAppConfig, event.port_app_config)
        old_entities, new_entities = await self.process_commit_changes(payload, config)
        logger.info(
            f"Processing push event with old_entities: {old_entities} and new_entities: {new_entities}"
        )
        await ocean.update_diff(
            {"before": old_entities, "after": new_entities},
            UserAgentType.gitops,
        )
        logger.debug("Completed diff upadte")
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def process_commit_changes(
        self,
        payload: EventPayload,
        config: BitbucketAppConfig,
    ) -> tuple[List[Any], List[Any]]:
        repo = payload.get("repository", {}).get("name", "")
        bitbucket_client = self._webhook_client

        all_old_entities = []
        all_new_entities = []

        async for (
            new_commit_hash,
            old_commit_hash,
            branch,
        ) in get_commit_hash_from_payload(payload):
            logger.debug(
                f"Processing commit: new={new_commit_hash}, old={old_commit_hash}, branch={branch}"
            )

            if config.branch and branch != config.branch:
                logger.debug(f"Skipping push event for branch: {branch}")
                continue

            old_entities, new_entities = await process_diff_stats(
                client=bitbucket_client,
                repo=repo,
                spec_paths=config.spec_path,
                old_hash=old_commit_hash,
                new_hash=new_commit_hash,
            )
            all_old_entities.extend(old_entities)
            all_new_entities.extend(new_entities)
        logger.debug(
            f"Old entities: {all_old_entities}, New entities: {all_new_entities}; _process_commits"
        )
        return all_old_entities, all_new_entities
