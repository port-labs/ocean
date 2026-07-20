import re
from typing import Any, Dict, Union, cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabProjectMemberSelector

# Events where group-hook payloads omit project_id but include project_path_with_namespace
_MEMBER_EVENTS = frozenset(
    {"user_add_to_team", "user_remove_from_team", "user_update_for_team"}
)


class ProjectWithMemberWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = [
        "project_create",
        "project_destroy",
        "user_add_to_team",
        "user_remove_from_team",
        "user_update_for_team",
    ]
    hooks = ["Project Hook", "Member Hook"]

    async def validate_payload(self, payload: EventPayload) -> bool:
        event_name = payload.get("event_name")
        if not event_name:
            return False

        # Group-hook member events carry project_path_with_namespace instead of project_id
        if event_name in _MEMBER_EVENTS:
            return bool(
                payload.get("project_id") or payload.get("project_path_with_namespace")
            )

        if "project_id" not in payload:
            return False

        if event_name in ("project_create", "project_destroy"):
            if {"name", "path", "path_with_namespace"} - payload.keys():
                return False

        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT_WITH_MEMBERS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # Ref for API lookup: _MEMBER_EVENTS allow project_id OR project_path_with_namespace;
        # project_create requires project_id plus name/path fields (see validate_payload).
        # project_destroy is handled below and does not use this ref for fetch.
        project_ref = cast(
            Union[str, int],
            payload.get("project_id") or payload.get("project_path_with_namespace"),
        )
        event_name = payload["event_name"]

        logger.info(
            f"Handling {event_name} webhook event for project with members, project ref '{project_ref}'"
        )

        if event_name == "project_destroy":
            deleted_project = self._parse_deleted_payload(payload)
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[deleted_project],
            )

        selector = cast(GitlabProjectMemberSelector, resource_config.selector)
        include_bot_members = bool(selector.include_bot_members)
        include_inherited_members = selector.include_inherited_members

        project = await self._gitlab_webhook_client.get_project(project_ref)
        if project:
            project = await self._gitlab_webhook_client.enrich_project_with_members(
                project,
                include_bot_members=include_bot_members,
                include_inherited_members=include_inherited_members,
            )
            return WebhookEventRawResults(
                updated_raw_results=[project],
                deleted_raw_results=[],
            )

        logger.warning(f"Project '{project_ref}' not found")
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

    def _strip_deleted_suffix(self, value: str) -> str:
        return re.sub(r"(-deleted)?-\d+$", "", value)

    def _parse_deleted_payload(self, payload: EventPayload) -> Dict[str, Any]:
        return {
            "id": payload["project_id"],
            "name": self._strip_deleted_suffix(payload["name"]),
            "path": self._strip_deleted_suffix(payload["path"]),
            "path_with_namespace": self._strip_deleted_suffix(
                payload["path_with_namespace"]
            ),
        }
