from typing import Any, Dict, List, Tuple

from loguru import logger
from azure_devops.misc import Kind
from azure_devops.webhooks.events import PushEvents
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


ZERO_OBJECT_ID = "0000000000000000000000000000000000000000"


class BranchWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.BRANCH]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            return event.payload.get("eventType") == PushEvents.PUSH
        except Exception:
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        resource = payload.get("resource", {})
        repository = resource.get("repository", {})
        ref_updates = resource.get("refUpdates")

        return (
            isinstance(ref_updates, list)
            and len(ref_updates) > 0
            and repository.get("id") is not None
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        resource = payload["resource"]
        repository_id = resource["repository"]["id"]

        repository = resource["repository"]
        if not repository:
            logger.warning(f"Repository with ID {repository_id} not found")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated, deleted = self._extract_branch_changes(
            resource["refUpdates"], repository
        )

        if updated:
            logger.info(
                f"Branch updates: {len(updated)} in repo {repository.get('name')}"
            )
        if deleted:
            logger.info(
                f"Branch deletions: {len(deleted)} in repo {repository.get('name')}"
            )

        return WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=deleted,
        )

    @staticmethod
    def _extract_branch_changes(
        ref_updates: List[Dict[str, Any]], repository: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        updated: List[Dict[str, Any]] = []
        deleted: List[Dict[str, Any]] = []

        for ref in ref_updates:
            ref_name = ref.get("name") or ""
            if not ref_name.startswith("refs/heads/"):
                continue

            branch_name = ref_name.replace("refs/heads/", "")
            new_oid = ref.get("newObjectId") or ""
            old_oid = ref.get("oldObjectId") or ""

            # Deletion when newObjectId is all zeros (per ADO semantics)
            if new_oid == ZERO_OBJECT_ID:
                deleted.append(
                    {
                        "name": branch_name,
                        "refName": ref_name,
                        "objectId": old_oid,
                        "__repository": repository,
                    }
                )
                continue

            updated.append(
                {
                    "name": branch_name,
                    "refName": ref_name,
                    "objectId": new_oid,
                    "__repository": repository,
                }
            )

        return updated, deleted
