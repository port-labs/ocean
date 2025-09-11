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

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        object_attrs = payload["object_attributes"]

        merge_request_id = object_attrs["iid"]
        project_id = payload["project"]["id"]
        state = object_attrs["state"]
        updated_at = parser.parse(object_attrs["updated_at"]).replace(
            tzinfo=timezone.utc
        )

        logger.info(
            f"Handling merge request webhook event for project {project_id} and merge request {merge_request_id} with state {state}"
        )

        config = cast(GitlabMergeRequestResourceConfig, resource_config)

        if state not in config.selector.states:
            logger.info(
                f"Deleting merge request {merge_request_id} as current state {state} does not match configured states {config.selector.states}."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[object_attrs],
            )

        if updated_at < config.selector.updated_after_datetime and state != "opened":
            logger.info(
                f"Deleting merge request {merge_request_id} as updated at {updated_at} is before {config.selector.updated_after_datetime}"
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
