from typing import cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.merge_request_comments import GITLAB_NOTEABLE_TYPE_MERGE_REQUEST
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.merge_request_webhook_shared import (
    handle_merge_request_webhook_event,
)
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabMergeRequestResourceConfig


class MergeRequestCommentWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["note"]
    hooks = ["Note Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MERGE_REQUEST]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await super().should_process_event(event):
            return False
        noteable_type = event.payload.get("object_attributes", {}).get("noteable_type")
        return noteable_type == GITLAB_NOTEABLE_TYPE_MERGE_REQUEST

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        config = cast(GitlabMergeRequestResourceConfig, resource_config)

        merge_request_payload = payload.get("merge_request")
        if not isinstance(merge_request_payload, dict):
            logger.warning(
                "Skipping merge request note event; missing merge_request in payload"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        project = payload.get("project")
        if not isinstance(project, dict):
            logger.warning(
                "Skipping merge request note event; missing project in payload"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        project_id = project.get("id")
        merge_request_iid = merge_request_payload.get("iid")
        if project_id is None or merge_request_iid is None:
            logger.warning(
                "Skipping merge request note event; missing project id or merge request iid"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        state = merge_request_payload.get("state", "")
        logger.info(
            f"Handling merge request note webhook for project {project_id} "
            f"merge request {merge_request_iid} (state={state})"
        )

        return await handle_merge_request_webhook_event(
            self._gitlab_webhook_client,
            config.selector,
            project_id=project_id,
            merge_request_iid=merge_request_iid,
            state=state,
            updated_at_raw=merge_request_payload.get("updated_at"),
            delete_payload=merge_request_payload,
            require_include_comments=True,
            include_comments_override=True,
        )
