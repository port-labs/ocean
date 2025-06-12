from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from dateutil import parser
from datetime import timezone

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabMergeRequestResourceConfig
from typing import cast


class MergeRequestWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["merge_request"]
    hooks = ["Merge Request Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MERGE_REQUEST]

    def _is_valid_state(self, state: str) -> bool:
        """Validate if the state is one of the allowed states."""
        return state in ["opened", "closed", "merged"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        object_attrs = payload["object_attributes"]

        merge_request_id = object_attrs["iid"]
        project_id = payload["project"]["id"]
        state = object_attrs["state"]
        created_at = parser.parse(object_attrs["created_at"]).replace(
            tzinfo=timezone.utc
        )

        logger.info(
            f"Handling merge request webhook event for project {project_id} and merge request {merge_request_id} with state {state}"
        )

        config = cast(GitlabMergeRequestResourceConfig, resource_config)

        if not self._is_valid_state(state):
            logger.info(
                f"Invalid state {state} for merge request {merge_request_id}. Skipping."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if state != config.selector.state:
            logger.info(
                f"State {state} does not match configured state {config.selector.state} for merge request {merge_request_id}. Skipping."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if created_at < config.selector.created_after_datetime:
            logger.info(
                f"Deleting merge request {merge_request_id} as created at {created_at} is before {config.selector.created_after_datetime}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[object_attrs],
            )

        merge_request = await self._gitlab_webhook_client.get_merge_request(
            project_id, merge_request_id
        )

        raw_merge_request_result = WebhookEventRawResults(
            updated_raw_results=[merge_request],
            deleted_raw_results=[],
        )

        logger.info(
            f"Successfully created result for merge request {merge_request_id} in {state} state"
        )

        return raw_merge_request_result
