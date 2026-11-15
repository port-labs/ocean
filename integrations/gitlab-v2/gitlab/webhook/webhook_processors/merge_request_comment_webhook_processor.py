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
        selector = config.selector
        if not selector.include_comments:
            logger.debug("Skipping merge request note event; includeComments is false")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

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

        state = merge_request_payload.get("state")
        logger.info(
            f"Handling merge request note webhook for project {project_id} "
            f"merge request {merge_request_iid} (state={state})"
        )

        if state not in selector.states:
            logger.info(
                f"Skipping merge request {merge_request_iid}; state {state} is not "
                f"in configured states {selector.states}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        merge_request = await self._gitlab_webhook_client.get_merge_request(
            project_id, merge_request_iid
        )
        if not merge_request:
            logger.warning(
                f"Merge request {merge_request_iid} in project {project_id} "
                "was not found, skipping upsert"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        enriched = await self._gitlab_webhook_client.enrich_merge_requests(
            [merge_request],
            enrich_with_commits=selector.enrich_with_commits,
            enrich_with_review_discussion=selector.enrich_with_review_discussion,
            include_comments=True,
            max_concurrent=1,
        )
        merge_request = enriched[0] if enriched else merge_request

        return WebhookEventRawResults(
            updated_raw_results=[merge_request],
            deleted_raw_results=[],
        )
