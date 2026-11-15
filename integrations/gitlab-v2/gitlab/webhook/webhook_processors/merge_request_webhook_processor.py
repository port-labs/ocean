from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.merge_request_webhook_shared import (
    handle_merge_request_webhook_event,
)
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

        logger.info(
            f"Handling merge request webhook event for project {project_id} and merge request {merge_request_id} with state {state}"
        )

        config = cast(GitlabMergeRequestResourceConfig, resource_config)
        result = await handle_merge_request_webhook_event(
            self._gitlab_webhook_client,
            config.selector,
            project_id=project_id,
            merge_request_iid=merge_request_id,
            state=state,
            updated_at_raw=object_attrs.get("updated_at"),
            delete_payload=object_attrs,
        )

        if result.updated_raw_results:
            logger.info(
                f"Successfully created result for merge request {merge_request_id} in {state} state"
            )

        return result
