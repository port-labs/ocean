from typing import cast, List, Any
from loguru import logger
from integration import BitbucketAppConfig
from gitops.generate_entities import get_commit_hash_from_payload
from client import BitbucketClient, ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from gitops.commit_processor import process_diff_stats


class PushWebhookProcessor(AbstractWebhookProcessor):
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
        all_updates, all_deletes = await self._process_commits(payload, config)

        return WebhookEventRawResults(
            updated_raw_results=[all_updates], deleted_raw_results=[all_deletes]
        )

    async def _process_commits(
        self,
        payload: EventPayload,
        config: BitbucketAppConfig,
    ) -> tuple[List[Any], List[Any]]:
        workspace = payload.get("repository", {}).get("workspace", {}).get("slug", "")
        repo = payload.get("repository", {}).get("name", "")
        client = BitbucketClient.create_from_ocean_config()

        all_updates = []
        all_deletes = []

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

            updates, deletes = await process_diff_stats(
                client=client,
                workspace=workspace,
                repo=repo,
                spec_paths=config.spec_path,
                old_hash=old_commit_hash,
                new_hash=new_commit_hash,
            )
            all_updates.extend(updates)
            all_deletes.extend(deletes)

        return all_updates, all_deletes
