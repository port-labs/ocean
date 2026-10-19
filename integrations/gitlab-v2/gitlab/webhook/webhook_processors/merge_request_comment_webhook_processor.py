from typing import Any, cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.merge_request_comments import (
    is_human_merge_request_note,
    normalize_merge_request_note,
)
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabMergeRequestCommentResourceConfig


class MergeRequestCommentWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["note"]
    hooks = ["Note Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MERGE_REQUEST_COMMENT]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await super().should_process_event(event):
            return False
        noteable_type = event.payload.get("object_attributes", {}).get("noteable_type")
        return noteable_type == "MergeRequest" and "merge_request" in event.payload

    async def validate_payload(self, payload: EventPayload) -> bool:
        attributes = payload.get("object_attributes")
        merge_request = payload.get("merge_request")
        return (
            isinstance(attributes, dict)
            and bool(attributes.get("id"))
            and isinstance(merge_request, dict)
            and merge_request.get("id") is not None
        )

    def _note_from_payload(self, payload: EventPayload) -> dict[str, Any]:
        attributes = payload["object_attributes"]
        user_raw = payload.get("user")
        user: dict[str, Any] = user_raw if isinstance(user_raw, dict) else {}
        return {
            **attributes,
            "body": attributes.get("note") or attributes.get("body") or "",
            "author": {"username": user.get("username") or user.get("name") or ""},
            "url": attributes.get("url"),
        }

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        config = cast(GitlabMergeRequestCommentResourceConfig, resource_config)
        merge_request = payload["merge_request"]
        note = self._note_from_payload(payload)
        normalized = normalize_merge_request_note(note, merge_request)
        state = merge_request.get("state")
        logger.info(
            f"Processing merge request note {normalized['__commentId']} in state {state}"
        )

        if state not in config.selector.states or not is_human_merge_request_note(
            note, config.selector.include_system_notes
        ):
            if note.get("system") and not config.selector.include_system_notes:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[normalized]
            )
        return WebhookEventRawResults(
            updated_raw_results=[normalized], deleted_raw_results=[]
        )
