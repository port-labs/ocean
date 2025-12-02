from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from datetime import datetime, timezone

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabIssueResourceConfig
from typing import cast


class IssueWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["issue"]
    hooks = ["Issue Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue_id = payload["object_attributes"]["iid"]
        project_id = payload["project"]["id"]
        logger.info(
            f"Handling issue webhook event for project {project_id} and issue {issue_id}"
        )

        object_attrs = payload.get("object_attributes", {})
        selector = cast(GitlabIssueResourceConfig, resource_config).selector
        should_process = True

        if selector.state and object_attrs.get("state") != selector.state:
            logger.info(
                f"Issue {issue_id} state '{object_attrs.get('state')}' does not match selector state '{selector.state}'"
            )
            should_process = False

        if selector.issue_type and should_process:
            webhook_type = object_attrs.get("type", "").lower()
            if webhook_type != selector.issue_type:
                logger.info(
                    f"Issue {issue_id} type '{webhook_type}' does not match selector type '{selector.issue_type}'"
                )
                should_process = False

        if selector.labels and should_process:
            required_labels = {label.strip() for label in selector.labels.split(",")}
            issue_label_titles = {
                label.get("title", "") for label in object_attrs.get("labels", [])
            }
            if not required_labels.issubset(issue_label_titles):
                logger.info(
                    f"Issue {issue_id} labels {issue_label_titles} do not contain all required labels {required_labels}"
                )
                should_process = False

        if selector.updated_after and should_process:
            updated_at_str = object_attrs.get("updated_at", "")
            if updated_at_str:
                issue_updated = datetime.strptime(
                    updated_at_str, "%Y-%m-%d %H:%M:%S %Z"
                ).replace(tzinfo=timezone.utc)
                cutoff_date = datetime.fromisoformat(selector.updated_after_datetime)
                if issue_updated < cutoff_date:
                    logger.info(
                        f"Issue {issue_id} updated at {issue_updated} is before cutoff {cutoff_date}"
                    )
                    should_process = False

        if not should_process:
            logger.info(
                f"Issue {issue_id} filtered out by selector criteria - skipping API call"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        issue = await self._gitlab_webhook_client.get_issue(project_id, issue_id)

        return WebhookEventRawResults(
            updated_raw_results=[issue],
            deleted_raw_results=[],
        )
